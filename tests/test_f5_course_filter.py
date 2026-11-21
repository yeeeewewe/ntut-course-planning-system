import unittest
from f5_course_filter import filter_and_check_courses


class TestF5CourseFilter(unittest.TestCase):
    def setUp(self):
        """建立符合 F1 規格的模擬課程測試資料（不依賴全域變數）"""
        self.sample_courses = [
            {
                "course_id": "CS101", "name": "計算機概論", "credits": 3, "type": "必修",
                "teacher": "王教授", "capacity": 50, "enrolled": 45, "room": "E101",
                "slots": [(1, '1'), (1, '2'), (1, '3')]
            },
            {
                "course_id": "CS102", "name": "Python程式設計", "credits": 3, "type": "必修",
                "teacher": "李教授", "capacity": 40, "enrolled": 40, "room": "E102",  # 已額滿
                "slots": [(2, '2'), (2, '3'), (2, '4')]
            },
            {
                "course_id": "MA101", "name": "微積分", "credits": 4, "type": "必修",
                "teacher": "張教授", "capacity": 60, "enrolled": 50, "room": "M201",
                "slots": [(3, '1'), (3, '2'), (5, '1'), (5, '2')]
            },
            {
                "course_id": "EN101", "name": "大一英文", "credits": 2, "type": "選修",
                "teacher": "陳教授", "capacity": 30, "enrolled": 20, "room": "L105",
                "slots": [(4, 'a'), (4, 'b')]  # 夜間/晚間節次 a, b
            },
            {
                "course_id": "GE201", "name": "心理學導論", "credits": 2, "type": "選修",
                "teacher": "林教授", "capacity": 50, "enrolled": 30, "room": "H301",
                "slots": [(1, '2'), (1, '3')]  # 與 CS101 衝堂
            },
            {
                "course_id": "GE202", "name": "經濟學原理", "credits": 3, "type": "選修",
                "teacher": "黃教授", "capacity": 45, "enrolled": 10, "room": "B102",
                "slots": [(5, '5'), (5, '6'), (5, '7')]
            }
        ]

    def test_scenario_1_normal_feasible(self):
        """情境 1：正常可行的選課條件，且正確依必修與偏好星期排序"""
        prefs = {
            "desired_courses": ["EN101", "GE202"],
            "required_courses": ["CS101", "MA101"],
            "min_credits": 9,
            "max_credits": 15,
            "unavailable_slots": [(4, '1')],
            "preferred_days": [1, 3, 5]
        }
        res = filter_and_check_courses(self.sample_courses, prefs)
        self.assertTrue(res["is_feasible"])
        self.assertEqual(len(res["errors"]), 0)
        # 驗證排序：必修(CS101, MA101) 在前，選修中符合星期5的 GE202 排在星期4的 EN101 前面
        candidate_ids = [c["course_id"] for c in res["candidates"]]
        self.assertEqual(candidate_ids, ["CS101", "MA101", "GE202", "EN101"])

    def test_scenario_2_required_course_full(self):
        """情境 2：課程額滿（必修課 CS102 已額滿導致不可行）"""
        prefs = {
            "desired_courses": ["EN101"],
            "required_courses": ["CS102"],  # CS102 40/40 額滿
            "min_credits": 2,
            "max_credits": 12,
            "unavailable_slots": [],
            "preferred_days": [2]
        }
        res = filter_and_check_courses(self.sample_courses, prefs)
        self.assertFalse(res["is_feasible"])
        self.assertTrue(any("必修額滿" in err for err in res["errors"]))

    def test_scenario_3_conflict_with_unavailable_slot(self):
        """情境 3：條件互相矛盾（必修課與不可上課時段衝突）"""
        prefs = {
            "desired_courses": ["GE202"],
            "required_courses": ["CS101"],  # CS101 在 (1, '1'), (1, '2'), (1, '3')
            "min_credits": 3,
            "max_credits": 12,
            "unavailable_slots": [(1, '2')],
            "preferred_days": [5]
        }
        res = filter_and_check_courses(self.sample_courses, prefs)
        self.assertFalse(res["is_feasible"])
        self.assertTrue(any("禁用時段衝突" in err for err in res["errors"]))

    def test_scenario_4_required_courses_time_conflict(self):
        """情境 4：條件互相矛盾（兩門必修課時段互衝）"""
        prefs = {
            "desired_courses": [],
            "required_courses": ["CS101", "GE201"],  # 兩者皆在星期1第2、3節上課
            "min_credits": 4,
            "max_credits": 12,
            "unavailable_slots": [],
            "preferred_days": [1]
        }
        res = filter_and_check_courses(self.sample_courses, prefs)
        self.assertFalse(res["is_feasible"])
        self.assertTrue(any("必修互衝" in err for err in res["errors"]))

    def test_scenario_5_insufficient_min_credits(self):
        """情境 5：無法滿足最低學分（選修課 CS102 因額滿被過濾後，剩餘總學分不足）"""
        prefs = {
            "desired_courses": ["CS102", "EN101", "GE202"],  # CS102 額滿被濾除，剩 2+3=5 學分
            "required_courses": [],
            "min_credits": 8,
            "max_credits": 15,
            "unavailable_slots": [],
            "preferred_days": [4, 5]
        }
        res = filter_and_check_courses(self.sample_courses, prefs)
        self.assertFalse(res["is_feasible"])
        self.assertTrue(any("無法滿足最低學分" in err for err in res["errors"]))
        self.assertTrue(any("已排除選修" in warn for warn in res["warnings"]))

    def test_scenario_6_credit_bounds_contradiction(self):
        """額外邊界測試：最低學分大於最高學分，且必修學分超過上限"""
        prefs = {
            "desired_courses": [],
            "required_courses": ["CS101", "MA101"],  # 必修共 7 學分
            "min_credits": 10,
            "max_credits": 6,  # 矛盾設定
            "unavailable_slots": [],
            "preferred_days": []
        }
        res = filter_and_check_courses(self.sample_courses, prefs)
        self.assertFalse(res["is_feasible"])
        self.assertGreaterEqual(len(res["errors"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)