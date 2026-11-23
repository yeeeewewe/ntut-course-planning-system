"""F6: JSON persistence utilities.

The storage layer is deliberately independent from F1 business modules.
Pass a validator when the caller knows the dataset's schema.

JSON object format:
{
  "record-key": {"id": "record-key", ...}
}

load_json() skips invalid individual records and reports them in LoadReport.
A syntactically malformed JSON document cannot be safely split into records;
in that case StorageFormatError is raised and the caller should keep the
current in-memory data / use a backup rather than silently overwrite the file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import tempfile
from typing import Callable, Any


class StorageError(Exception):
    """Base exception for storage operations."""


class StorageFormatError(StorageError):
    """The JSON document itself cannot be parsed or has an invalid root."""


@dataclass
class LoadReport:
    data: dict[str, dict]
    loaded_count: int
    skipped_count: int = 0
    errors: list[str] = field(default_factory=list)


RecordValidator = Callable[[dict], bool]


def save_json(path: str | Path, data: dict, *, indent: int = 4) -> None:
    """Atomically save a dictionary as UTF-8 JSON.

    The parent directory is created if needed. The original file is not
    replaced unless serialization and writing both succeed.
    """
    target = Path(path)
    if not isinstance(data, dict):
        raise TypeError("data 必須是 dict")

    target.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_name = temp_file.name
            json.dump(data, temp_file, ensure_ascii=False, indent=indent)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_name, target)
    except (OSError, TypeError, ValueError) as exc:
        if temp_name:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
        raise StorageError(f"無法儲存 {target}: {exc}") from exc


def load_json(
    path: str | Path,
    *,
    validator: RecordValidator | None = None,
    key_field: str | None = "id",
) -> LoadReport:
    """Load valid records from a JSON object.

    Invalid individual records are skipped and listed in errors. When
    key_field is not None, each record must be a dict and its key_field
    must equal the outer JSON key. If validator is supplied, it must return
    True for a valid record.

    Missing file means an empty dataset. Malformed JSON or a non-object root
    raises StorageFormatError so callers do not mistake corruption for empty
    data and accidentally overwrite the source.
    """
    source = Path(path)
    if not source.exists():
        return LoadReport(data={}, loaded_count=0)

    try:
        with source.open("r", encoding="utf-8") as file:
            raw = json.load(file)
    except json.JSONDecodeError as exc:
        raise StorageFormatError(
            f"{source} JSON 格式錯誤（行 {exc.lineno}，列 {exc.colno}）"
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise StorageError(f"無法讀取 {source}: {exc}") from exc

    if not isinstance(raw, dict):
        raise StorageFormatError(f"{source} 根節點必須是 JSON object")

    valid: dict[str, dict] = {}
    errors: list[str] = []
    for record_key, record in raw.items():
        reason = None
        if not isinstance(record_key, str) or not record_key.strip():
            reason = "資料鍵必須是非空字串"
        elif not isinstance(record, dict):
            reason = "資料內容必須是 object"
        elif key_field is not None and record.get(key_field) != record_key:
            reason = f"{key_field} 必須與外層資料鍵相同"
        elif validator is not None:
            try:
                if validator(record) is not True:
                    reason = "未通過資料驗證"
            except Exception as exc:  # validator boundary: isolate this record
                reason = f"驗證函式發生錯誤：{type(exc).__name__}: {exc}"

        if reason:
            errors.append(f"{record_key!r}: {reason}")
        else:
            valid[record_key] = record

    return LoadReport(
        data=valid,
        loaded_count=len(valid),
        skipped_count=len(errors),
        errors=errors,
    )


def save_dataset_bundle(directory: str | Path, datasets: dict[str, dict]) -> None:
    """Save named datasets as <name>.json files.

    Example dataset names: courses, students, classrooms, activities,
    enrollments. The caller supplies the schema-correct dictionaries.
    """
    if not isinstance(datasets, dict):
        raise TypeError("datasets 必須是 dict")
    base = Path(directory)
    for name, data in datasets.items():
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise ValueError(f"不合法的資料集名稱：{name!r}")
        save_json(base / f"{name}.json", data)


def load_dataset_bundle(
    directory: str | Path,
    *,
    validators: dict[str, RecordValidator] | None = None,
) -> dict[str, LoadReport]:
    """Load the five F6 datasets independently.

    Validators can be supplied for datasets whose final schema is agreed.
    A broken file is reported independently; other dataset files still load.
    """
    base = Path(directory)
    validators = validators or {}
    names = ("courses", "students", "classrooms", "activities", "enrollments")
    reports: dict[str, LoadReport] = {}
    for name in names:
        try:
            reports[name] = load_json(
                base / f"{name}.json",
                validator=validators.get(name),
                key_field="id",
            )
        except StorageError as exc:
            reports[name] = LoadReport(
                data={}, loaded_count=0, skipped_count=1,
                errors=[str(exc)],
            )
    return reports
