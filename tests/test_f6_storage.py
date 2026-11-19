"""F6 automated tests: run from repository root with
python -m unittest discover -s tests -p "test_f6_storage.py" -v
"""
import json
from pathlib import Path
import tempfile
import unittest

from modules.storage import (
    StorageError, StorageFormatError, load_json, save_json,
    load_dataset_bundle, save_dataset_bundle,
)


def valid_record(record):
    return isinstance(record, dict) and isinstance(record.get("id"), str) and bool(record["id"].strip())


class TestF6NormalCases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_01_save_dict_creates_file(self):
        p = self.base / "x.json"; save_json(p, {"A": {"id": "A"}}); self.assertTrue(p.exists())

    def test_02_saved_json_can_be_loaded(self):
        p = self.base / "x.json"; save_json(p, {"A": {"id": "A"}}); self.assertEqual(load_json(p).data["A"]["id"], "A")

    def test_03_chinese_text_is_preserved(self):
        p = self.base / "x.json"; save_json(p, {"A": {"id": "A", "name": "程式設計"}}); self.assertIn("程式設計", p.read_text(encoding="utf-8"))

    def test_04_nested_lists_round_trip(self):
        d = {"A": {"id": "A", "schedule": [[1, 1], [1, 2]]}}; p = self.base / "x.json"; save_json(p, d); self.assertEqual(load_json(p).data, d)

    def test_05_multiple_records_round_trip(self):
        d = {str(i): {"id": str(i)} for i in range(5)}; p = self.base / "x.json"; save_json(p, d); self.assertEqual(load_json(p).data, d)

    def test_06_load_report_counts_valid_records(self):
        p = self.base / "x.json"; save_json(p, {"A": {"id": "A"}}); r = load_json(p); self.assertEqual(r.loaded_count, 1)

    def test_07_missing_file_returns_empty_dataset(self):
        r = load_json(self.base / "missing.json"); self.assertEqual(r.data, {}); self.assertEqual(r.loaded_count, 0)

    def test_08_save_creates_parent_directory(self):
        p = self.base / "new" / "nested" / "x.json"; save_json(p, {}); self.assertTrue(p.exists())

    def test_09_dataset_bundle_saves_five_files(self):
        names = {n: {} for n in ("courses", "students", "classrooms", "activities", "enrollments")}; save_dataset_bundle(self.base, names); self.assertTrue(all((self.base / f"{n}.json").exists() for n in names))

    def test_10_bundle_loads_datasets_independently(self):
        save_dataset_bundle(self.base, {"courses": {"C1": {"id": "C1"}}}); r = load_dataset_bundle(self.base); self.assertEqual(r["courses"].loaded_count, 1); self.assertEqual(r["students"].data, {})


class TestF6BoundaryCases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_11_empty_dictionary(self):
        p = self.base / "x.json"; save_json(p, {}); self.assertEqual(load_json(p).data, {})

    def test_12_one_record(self):
        p = self.base / "x.json"; save_json(p, {"A": {"id": "A"}}); self.assertEqual(len(load_json(p).data), 1)

    def test_13_many_records(self):
        d = {f"C{i}": {"id": f"C{i}"} for i in range(1000)}; p = self.base / "x.json"; save_json(p, d); self.assertEqual(load_json(p).loaded_count, 1000)

    def test_14_zero_numeric_value_is_preserved(self):
        d = {"A": {"id": "A", "value": 0}}; p = self.base / "x.json"; save_json(p, d); self.assertEqual(load_json(p).data, d)

    def test_15_false_boolean_is_preserved(self):
        d = {"A": {"id": "A", "required": False}}; p = self.base / "x.json"; save_json(p, d); self.assertIs(load_json(p).data["A"]["required"], False)

    def test_16_empty_list_is_preserved(self):
        d = {"A": {"id": "A", "items": []}}; p = self.base / "x.json"; save_json(p, d); self.assertEqual(load_json(p).data, d)

    def test_17_none_value_is_preserved(self):
        d = {"A": {"id": "A", "optional": None}}; p = self.base / "x.json"; save_json(p, d); self.assertEqual(load_json(p).data, d)

    def test_18_no_validator_accepts_unknown_record_fields(self):
        p = self.base / "x.json"; save_json(p, {"A": {"id": "A", "extra": "x"}}); self.assertIn("A", load_json(p).data)

    def test_19_validator_accepts_valid_record(self):
        p = self.base / "x.json"; save_json(p, {"A": {"id": "A"}}); self.assertEqual(load_json(p, validator=valid_record).loaded_count, 1)

    def test_20_indent_parameter_is_supported(self):
        p = self.base / "x.json"; save_json(p, {"A": {"id": "A"}}, indent=2); self.assertIn('\n  "A"', p.read_text(encoding="utf-8"))


class TestF6ErrorAndConflictCases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_21_reject_non_dictionary_save_data(self):
        with self.assertRaises(TypeError): save_json(self.base / "x.json", [])

    def test_22_reject_malformed_json_document(self):
        p = self.base / "x.json"; p.write_text('{"A": ', encoding="utf-8")
        with self.assertRaises(StorageFormatError): load_json(p)

    def test_23_reject_json_array_root(self):
        p = self.base / "x.json"; p.write_text('[]', encoding="utf-8")
        with self.assertRaises(StorageFormatError): load_json(p)

    def test_24_reject_json_scalar_root(self):
        p = self.base / "x.json"; p.write_text('"text"', encoding="utf-8")
        with self.assertRaises(StorageFormatError): load_json(p)

    def test_25_skip_non_object_record(self):
        p = self.base / "x.json"; p.write_text(json.dumps({"A": 123}), encoding="utf-8")
        r = load_json(p); self.assertEqual(r.skipped_count, 1); self.assertEqual(r.data, {})

    def test_26_skip_record_with_mismatched_id(self):
        p = self.base / "x.json"; save_json(p, {"A": {"id": "B"}})
        self.assertEqual(load_json(p).skipped_count, 1)

    def test_27_skip_record_rejected_by_validator(self):
        p = self.base / "x.json"; save_json(p, {"A": {"id": "A"}, "B": {"id": ""}})
        r = load_json(p, validator=valid_record); self.assertEqual(set(r.data), {"A"}); self.assertEqual(r.skipped_count, 1)

    def test_28_keep_good_record_when_another_record_is_bad(self):
        p = self.base / "x.json"; save_json(p, {"GOOD": {"id": "GOOD"}, "BAD": 99})
        r = load_json(p); self.assertIn("GOOD", r.data); self.assertEqual(r.skipped_count, 1)

    def test_29_validator_exception_does_not_abort_other_records(self):
        def validator(record):
            if record["id"] == "BAD": raise ValueError("bad row")
            return True
        p = self.base / "x.json"; save_json(p, {"GOOD": {"id": "GOOD"}, "BAD": {"id": "BAD"}})
        r = load_json(p, validator=validator); self.assertEqual(set(r.data), {"GOOD"})

    def test_30_bundle_continues_when_one_file_has_bad_json(self):
        save_json(self.base / "courses.json", {"C1": {"id": "C1"}})
        (self.base / "students.json").write_text("{oops", encoding="utf-8")
        r = load_dataset_bundle(self.base); self.assertEqual(r["courses"].loaded_count, 1); self.assertTrue(r["students"].errors)

    def test_31_bundle_reports_bad_file_without_aborting_other_files(self):
        save_json(self.base / "courses.json", {"C1": {"id": "C1"}})
        save_json(self.base / "classrooms.json", {"R1": {"id": "R1"}})
        (self.base / "students.json").write_text("not-json", encoding="utf-8")
        r = load_dataset_bundle(self.base); self.assertEqual(r["courses"].loaded_count, 1); self.assertEqual(r["classrooms"].loaded_count, 1)

    def test_32_reject_invalid_dataset_name(self):
        with self.assertRaises(ValueError): save_dataset_bundle(self.base, {"../escape": {}})

    def test_33_reject_non_dictionary_bundle(self):
        with self.assertRaises(TypeError): save_dataset_bundle(self.base, [])

    def test_34_existing_file_remains_readable_after_successful_replacement(self):
        p = self.base / "x.json"; save_json(p, {"A": {"id": "A"}}); save_json(p, {"B": {"id": "B"}}); self.assertEqual(set(load_json(p).data), {"B"})

    def test_35_load_report_errors_are_recorded(self):
        p = self.base / "x.json"; save_json(p, {"A": 1}); r = load_json(p); self.assertEqual(len(r.errors), 1); self.assertIn("A", r.errors[0])

    def test_36_non_string_record_key_is_not_emitted_by_json_writer(self):
        # JSON object keys are strings after serialization; this confirms the
        # loader contract is based on the string key representation.
        p = self.base / "x.json"; p.write_text('{"1": {"id": "1"}}', encoding="utf-8")
        self.assertIn("1", load_json(p).data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
