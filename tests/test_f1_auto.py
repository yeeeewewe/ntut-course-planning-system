"""F1 課程／學生資料管理自動化測試。

在專案根目錄執行：python -m unittest discover -s tests -p "test_f1_auto.py" -v
只使用 Python 標準函式庫 unittest，不會讀寫正式 JSON 資料檔。
"""
import copy
import os
import sys
import unittest

# 讓此測試檔可由專案根目錄或 tests/ 目錄執行
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.course import (
    validate_course, add_course, update_course, can_delete_course,
    delete_course, search_course,
)
from modules.student import (
    validate_student, add_student, update_student, delete_student,
    search_student,
)


def course(cid="CS101", **overrides):
    data = {
        "id": cid, "name": "程式設計", "credits": 3, "required": True,
        "teacher": "王老師", "capacity": 2, "room": "教室A",
        "schedule": [[1, 1], [1, 2]],
    }
    data.update(overrides)
    return data


def student(sid="S001", enrolled=None, **overrides):
    data = {
        "id": sid, "name": "測試學生", "department": "資工系",
        "enrolled_courses": list(enrolled or []), "credit_limit": 25,
    }
    data.update(overrides)
    return data


def base_data():
    courses = {
        "CS101": course("CS101"),
        "CS201": course("CS201", name="資料結構", teacher="李老師",
                         required=False, capacity=3, schedule=[[2, 3]]),
        "EE101": course("EE101", name="電路學", teacher="王老師",
                         schedule=[[3, "a"]]),
    }
    students = {
        "S001": student("S001", ["CS101"]),
        "S002": student("S002", ["CS201"]),
    }
    return courses, students


class TestCourseValidation(unittest.TestCase):
    def test_valid_course(self):
        self.assertTrue(validate_course(course()))

    def test_non_dict_rejected(self):
        self.assertFalse(validate_course(None))

    def test_missing_or_extra_field_rejected(self):
        c = course(); del c["room"]
        self.assertFalse(validate_course(c))
        c = course(); c["extra"] = 1
        self.assertFalse(validate_course(c))

    def test_blank_text_rejected(self):
        for field in ("id", "name", "teacher", "room"):
            with self.subTest(field=field):
                self.assertFalse(validate_course(course(**{field: "  "})))

    def test_credits_and_capacity_must_be_positive_int(self):
        for field in ("credits", "capacity"):
            for value in (0, -1, True, 1.5, "2"):
                with self.subTest(field=field, value=value):
                    self.assertFalse(validate_course(course(**{field: value})))

    def test_required_must_be_bool(self):
        for value in (0, 1, "True", None):
            self.assertFalse(validate_course(course(required=value)))

    def test_schedule_must_be_nonempty_list(self):
        for value in (None, [], "1-2", [[1, 1, 2]]):
            self.assertFalse(validate_course(course(schedule=value)))

    def test_invalid_day_and_period_rejected(self):
        for slot in ([[0, 1]], [[8, 1]], [[True, 1]], [[1, 0]], [[1, 10]], [[1, "d"]]):
            with self.subTest(slot=slot):
                self.assertFalse(validate_course(course(schedule=slot)))

    def test_duplicate_slot_rejected(self):
        self.assertFalse(validate_course(course(schedule=[[1, 1], [1, 1]])))

    def test_valid_special_periods(self):
        self.assertTrue(validate_course(course(schedule=[[7, "a"], [7, "b"], [7, "c"]])))

    def test_validation_does_not_mutate_input(self):
        c = course(); before = copy.deepcopy(c)
        validate_course(c)
        self.assertEqual(c, before)


class TestCourseMutation(unittest.TestCase):
    def test_add_course_success(self):
        courses = {}
        self.assertTrue(add_course(courses, course()))
        self.assertEqual(courses["CS101"]["name"], "程式設計")

    def test_add_duplicate_id_fails_without_mutation(self):
        courses, _ = base_data(); before = copy.deepcopy(courses)
        self.assertFalse(add_course(courses, course("CS101", name="不應覆蓋")))
        self.assertEqual(courses, before)

    def test_add_invalid_course_fails_without_mutation(self):
        courses = {}; bad = course(credits=0)
        self.assertFalse(add_course(courses, bad))
        self.assertEqual(courses, {})

    def test_add_course_deep_copies_input(self):
        courses = {}; new = course()
        self.assertTrue(add_course(courses, new))
        new["schedule"][0][0] = 7
        self.assertEqual(courses["CS101"]["schedule"][0][0], 1)

    def test_update_course_success_and_preserves_other_fields(self):
        courses, _ = base_data()
        self.assertTrue(update_course(courses, "CS101", {"teacher": "陳老師"}))
        self.assertEqual(courses["CS101"]["teacher"], "陳老師")
        self.assertEqual(courses["CS101"]["credits"], 3)

    def test_update_course_rejects_empty_changes_id_and_unknown_field(self):
        for changes in ({}, {"id": "CS999"}, {"unknown": 1}):
            courses, _ = base_data(); before = copy.deepcopy(courses)
            self.assertFalse(update_course(courses, "CS101", changes))
            self.assertEqual(courses, before)

    def test_update_course_rejects_invalid_candidate_atomically(self):
        courses, _ = base_data(); before = copy.deepcopy(courses)
        self.assertFalse(update_course(courses, "CS101", {"credits": 0}))
        self.assertEqual(courses, before)

    def test_update_missing_course_fails(self):
        courses, _ = base_data()
        self.assertFalse(update_course(courses, "NOPE", {"teacher": "陳老師"}))

    def test_can_delete_course_rules(self):
        courses, students = base_data()
        self.assertFalse(can_delete_course(courses, "CS101", students))
        self.assertTrue(can_delete_course(courses, "EE101", students))
        self.assertFalse(can_delete_course(courses, "NOPE", students))

    def test_delete_enrolled_course_fails_atomically(self):
        courses, students = base_data(); before_c = copy.deepcopy(courses); before_s = copy.deepcopy(students)
        self.assertFalse(delete_course(courses, "CS101", students))
        self.assertEqual(courses, before_c); self.assertEqual(students, before_s)

    def test_delete_unenrolled_course_succeeds(self):
        courses, students = base_data(); before_s = copy.deepcopy(students)
        self.assertTrue(delete_course(courses, "EE101", students))
        self.assertNotIn("EE101", courses)
        self.assertEqual(students, before_s)


class TestCourseSearch(unittest.TestCase):
    def test_search_all_sorted_by_id(self):
        courses, students = base_data()
        self.assertEqual([c["id"] for c in search_course(courses, students)], ["CS101", "CS201", "EE101"])

    def test_search_combines_filters_with_and(self):
        courses, students = base_data()
        results = search_course(courses, students, teacher="王老師", day=1, required=True)
        self.assertEqual([c["id"] for c in results], ["CS101"])

    def test_search_min_remaining_uses_enrollment_count(self):
        courses, students = base_data()
        self.assertEqual([c["id"] for c in search_course(courses, students, min_remaining=2)], ["CS201", "EE101"])

    def test_search_no_match_returns_empty_list(self):
        courses, students = base_data()
        self.assertEqual(search_course(courses, students, course_id="NOPE"), [])

    def test_search_invalid_query_raises_value_error(self):
        courses, students = base_data()
        for kwargs in ({"day": 8}, {"day": True}, {"teacher": " "}, {"required": 1}, {"min_remaining": -1}, {"min_remaining": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                search_course(courses, students, **kwargs)

    def test_search_result_nested_data_is_independent(self):
        courses, students = base_data(); before = copy.deepcopy(courses)
        results = search_course(courses, students, course_id="CS101")
        results[0]["schedule"][0][0] = 7
        self.assertEqual(courses, before)


class TestStudentFunctions(unittest.TestCase):
    def test_validate_student_empty_and_valid_enrollment(self):
        courses, _ = base_data()
        self.assertTrue(validate_student(student("S010"), courses))
        self.assertTrue(validate_student(student("S011", ["CS101"]), courses))

    def test_validate_student_rejects_bad_reference_and_duplicate_enrollment(self):
        courses, _ = base_data()
        self.assertFalse(validate_student(student("S010", ["NOPE"]), courses))
        self.assertFalse(validate_student(student("S010", ["CS101", "CS101"]), courses))

    def test_validate_student_rejects_invalid_shape_and_credit_limit(self):
        courses, _ = base_data()
        bad = student(); del bad["department"]
        self.assertFalse(validate_student(bad, courses))
        for value in (0, -1, True, 2.5):
            self.assertFalse(validate_student(student(credit_limit=value), courses))

    def test_add_student_success_and_duplicate_failure(self):
        courses, students = base_data()
        self.assertTrue(add_student(students, student("S003", ["CS201"]), courses))
        before = copy.deepcopy(students)
        self.assertFalse(add_student(students, student("S001"), courses))
        self.assertEqual(students, before)

    def test_add_student_invalid_reference_fails_atomically(self):
        courses, students = base_data(); before = copy.deepcopy(students)
        self.assertFalse(add_student(students, student("S003", ["NOPE"]), courses))
        self.assertEqual(students, before)

    def test_add_student_deep_copies_input(self):
        courses, students = base_data(); new = student("S003", ["CS101"])
        self.assertTrue(add_student(students, new, courses))
        new["enrolled_courses"].append("CS201")
        self.assertEqual(students["S003"]["enrolled_courses"], ["CS101"])

    def test_update_student_success_and_preserves_fields(self):
        courses, students = base_data()
        self.assertTrue(update_student(students, "S001", {"department": "電機系"}, courses))
        self.assertEqual(students["S001"]["department"], "電機系")
        self.assertEqual(students["S001"]["enrolled_courses"], ["CS101"])

    def test_update_student_rejects_empty_id_and_invalid_changes(self):
        for sid, changes in (("S001", {}), ("S001", {"id": "S999"}), ("NOPE", {"name": "新名字"}), ("S001", {"enrolled_courses": ["NOPE"]})):
            courses, students = base_data(); before = copy.deepcopy(students)
            self.assertFalse(update_student(students, sid, changes, courses))
            self.assertEqual(students, before)

    def test_delete_student_with_enrollment(self):
        _, students = base_data()
        self.assertTrue(delete_student(students, "S001"))
        self.assertNotIn("S001", students)
        self.assertFalse(delete_student(students, "S001"))

    def test_search_student_sorted_and_missing_result(self):
        _, students = base_data()
        self.assertEqual([s["id"] for s in search_student(students)], ["S001", "S002"])
        self.assertEqual(search_student(students, student_id="NOPE"), [])

    def test_search_student_invalid_id_raises_value_error(self):
        _, students = base_data()
        for sid in (" ", 123, True):
            with self.subTest(sid=sid), self.assertRaises(ValueError):
                search_student(students, student_id=sid)

    def test_search_student_nested_result_is_independent(self):
        _, students = base_data(); before = copy.deepcopy(students)
        result = search_student(students, student_id="S001")
        result[0]["enrolled_courses"].clear()
        self.assertEqual(students, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
