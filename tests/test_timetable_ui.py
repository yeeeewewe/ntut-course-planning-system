import io
import unittest
from contextlib import redirect_stdout

from modules.timetable import build_timetable
from modules.timetable_ui import timetable_action, timetable_menu, PERIODS


class TestTimetableUI(unittest.TestCase):
    def setUp(self):
        self.courses = {
            key: dict(id=key, name=key, credits=3, required=False,
                      teacher="T", capacity=20, room=key, schedule=schedule)
            for key, schedule in {"C1": [[1, 1], [1, 5], [3, 2]],
                                  "C2": [[1, 9]]}.items()
        }
        self.student = dict(id="S1", name="S", department="D", credit_limit=24,
                            enrolled_courses=["C1", "C2"])
        self.table = build_timetable(self.courses, self.student, [], week_start="2026-11-16")

    def action(self, choice, values):
        inputs = iter(values)
        output = io.StringIO()
        with redirect_stdout(output):
            timetable_action(choice, self.table, lambda _: next(inputs))
        return output.getvalue()

    def test_matrix_preserves_repeated_courses_and_same_day_courses(self):
        output = self.action("1", [])
        lines = output.splitlines()
        self.assertEqual(len(lines), 14)
        self.assertEqual([cell.strip() for cell in lines[1].split("|")],
                         ["節次", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"])
        self.assertEqual(output.count("C1"), 3)
        self.assertEqual(lines[2].split("|")[1].strip(), "C1")
        self.assertEqual(lines[3].split("|")[3].strip(), "C1")
        self.assertEqual(lines[10].split("|")[1].strip(), "C2")
        self.assertNotIn("[課程]", output)

    def test_query_combines_conditions(self):
        output = self.action("2", ["15", "15", "C1"])
        self.assertIn("第5節", output)
        self.assertIn("C1", output)
        self.assertNotIn("C2", output)

    def test_three_free_periods_and_cross_day(self):
        output = self.action("3", ["11", "23", ""])
        self.assertIn("星期一：第2節、第3節、第4節（連續 3 節）", output)
        self.assertIn("星期二：第1節、第2節、第3節（連續 3 節）", output)
        self.assertIn("星期一：第a節、第b節、第c節（連續 3 節）", output)

    def test_statistics(self):
        output = self.action("4", [])
        self.assertIn("星期一：上課 3 節，空堂 6 節", output)
        self.assertIn("每週總學分：6", output)

    def test_menu_activity_is_mapped_and_invalid_input_recovers(self):
        clock = [value for index, _ in enumerate(PERIODS)
                 for value in (f"{8+index:02d}:00", f"{8+index:02d}:45")]
        inputs = iter(["S1", "2", "bad", "",
                       "5", "A1", "Meeting", "1", "08:10", "08:30", *clock,
                       "", "1", "", "0"])
        output = io.StringIO()
        with redirect_stdout(output):
            timetable_menu(self.courses, {"S1": self.student},
                           lambda _: next(inputs), lambda *args, **kwargs: None)
        self.assertIn("操作失敗", output.getvalue())
        self.assertIn("C1/A1", output.getvalue())
        self.assertNotIn("[課程]", output.getvalue())

    def test_range_1c_to_52_includes_every_slot_and_both_endpoints(self):
        lines = self.action("2", ["1c", "52", ""]).splitlines()
        self.assertEqual(len(lines), 40)
        self.assertTrue(lines[1].startswith("星期一 第c節："))
        self.assertTrue(lines[-1].startswith("星期五 第2節："))
        self.assertIn("[課程] C1 C1", "\n".join(lines))
        self.assertNotIn("星期一 第9節：", "\n".join(lines))

    def test_invalid_and_reversed_ranges(self):
        for values in (["10"], ["81"], ["1d"], ["111"], ["52", "1c"]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.action("2", values)


if __name__ == "__main__":
    unittest.main()
