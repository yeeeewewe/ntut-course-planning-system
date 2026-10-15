"""F1 課程資料管理核心函式。

資料格式與對外契約分別見 data_model.docx、function_interface.docx。
教室存在性與跨模組可行性由呼叫端確認；本模組不讀寫 JSON。
"""

from copy import deepcopy as _deepcopy


def validate_course(course) -> bool:
    """檢查完整課程資料；合法為 True，否則 False，不修改輸入。

    只驗證欄位、型別與合法值，不檢查集合內代號重複、教室存在性
    或衝堂等跨模組條件。
    """
    if not isinstance(course, dict):
        return False

    required_fields = {
        "id", "name", "credits", "required",
        "teacher", "capacity", "room", "schedule",
    }
    if course.keys() != required_fields:
        return False

    for field in ("id", "name", "teacher", "room"):
        value = course[field]
        if not isinstance(value, str) or not value.strip():
            return False

    for field in ("credits", "capacity"):
        value = course[field]
        if type(value) is not int or value < 1:
            return False

    if type(course["required"]) is not bool:
        return False

    schedule = course["schedule"]
    if not isinstance(schedule, list) or not schedule:
        return False

    seen_slots = set()
    for slot in schedule:
        if not isinstance(slot, list) or len(slot) != 2:
            return False

        day, period = slot
        if type(day) is not int or not 1 <= day <= 7:
            return False

        valid_period = (
            type(period) is int and 1 <= period <= 9
        ) or (
            isinstance(period, str) and period in ("a", "b", "c")
        )
        if not valid_period:
            return False

        slot_key = (day, period)
        if slot_key in seen_slots:
            return False
        seen_slots.add(slot_key)

    return True


def add_course(courses, new_course) -> bool:
    """將合法且代號未重複的課程加入 courses，成功為 True。

    courses 須為符合資料模型的既有集合；呼叫端須先確認教室存在，
    並完成其流程要求的跨模組檢查。一般失敗為 False，輸入維持原狀。
    """
    if not isinstance(courses, dict) or not validate_course(new_course):
        return False

    course_id = new_course["id"]
    if course_id in courses:
        return False

    stored_course = _deepcopy(new_course)
    courses[course_id] = stored_course
    return True


def update_course(courses, course_id, changes) -> bool:
    """部分更新指定課程，成功為 True，一般失敗為 False。

    拒絕空 changes 及任何 id 欄位；保留未指定欄位，驗證候選完整
    課程後才寫入。教室與跨模組檢查由呼叫端負責，失敗時輸入不變。
    """
    if not isinstance(courses, dict):
        return False
    if not isinstance(course_id, str) or not course_id.strip():
        return False
    if not isinstance(changes, dict) or not changes or "id" in changes:
        return False
    if course_id not in courses:
        return False

    existing_course = courses[course_id]
    if not isinstance(existing_course, dict):
        return False

    candidate = existing_course.copy()
    candidate.update(changes)
    if not validate_course(candidate) or candidate["id"] != course_id:
        return False

    stored_course = _deepcopy(candidate)
    courses[course_id] = stored_course
    return True


def can_delete_course(courses, course_id, students) -> bool:
    """課程存在且沒有學生選修時回傳 True，所有輸入維持不變。

    呼叫端須提供完整且符合資料模型的選課現況；本函式不執行退選、
    課程取消或刪除，也不保留檢查結果供後續刪除沿用。
    """
    if not isinstance(courses, dict) or not isinstance(students, dict):
        return False
    if not isinstance(course_id, str) or not course_id.strip():
        return False
    if course_id not in courses:
        return False

    for student in students.values():
        if not isinstance(student, dict):
            return False
        enrolled_courses = student.get("enrolled_courses")
        if not isinstance(enrolled_courses, list):
            return False
        if course_id in enrolled_courses:
            return False

    return True


def delete_course(courses, course_id, students) -> bool:
    """重新檢查刪除限制，成功刪除為 True，否則 False 且資料不變。

    不沿用先前的檢查結果；仍有學生選修時拒絕刪除，不修改學生資料。
    """
    if not can_delete_course(courses, course_id, students):
        return False

    del courses[course_id]
    return True


def search_course(
    courses, students, *, course_id=None, teacher=None, day=None,
    required=None, min_remaining=None,
) -> list[dict]:
    """以 AND 組合條件查詢，依課程 id 字串排序並回傳獨立資料。

    兩集合須符合資料模型，students 須包含完整有效選課現況。
    None 略過條件；非法查詢參數拋出 ValueError，無結果回傳 []。
    剩餘名額由學生選課資料計算，所有輸入維持不變。
    """
    if not isinstance(courses, dict) or not isinstance(students, dict):
        raise ValueError("courses 與 students 必須是 dict")

    for field, value in (("course_id", course_id), ("teacher", teacher)):
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} 必須是非空白 str 或 None")

    if day is not None:
        if type(day) is not int or not 1 <= day <= 7:
            raise ValueError("day 必須是 1～7 的 int 或 None，不接受 bool")
    if required is not None and type(required) is not bool:
        raise ValueError("required 必須是 bool 或 None")
    if min_remaining is not None:
        if type(min_remaining) is not int or min_remaining < 0:
            raise ValueError("min_remaining 必須是非負 int 或 None，不接受 bool")

    results = []
    for course in courses.values():
        if course_id is not None and course["id"] != course_id:
            continue
        if teacher is not None and course["teacher"] != teacher:
            continue
        if day is not None and not any(slot[0] == day for slot in course["schedule"]):
            continue
        if required is not None and course["required"] != required:
            continue
        if min_remaining is not None:
            enrolled_count = sum(
                1 for student in students.values()
                if course["id"] in student["enrolled_courses"]
            )
            if course["capacity"] - enrolled_count < min_remaining:
                continue

        results.append(_deepcopy(course))

    results.sort(key=lambda course: course["id"])
    return results
