import io
import unittest
from contextlib import redirect_stdout

from modules.activity_ui import activity_action, activity_menu, input_activity
from modules.activity import add_activity
from modules.period_times import default_period_times


class TestActivityUI(unittest.TestCase):
    def setUp(self):
        self.activities = {}
        self.rooms = {"R1": dict(id="R1", capacity=2, equipment=["投影機"])}
        self.students = {f"S{i}": dict(id=f"S{i}", name="學生", department="資工",
                                     credit_limit=25, enrolled_courses=[]) for i in range(3)}
        self.clock = [dict(period=p, start=f"{h:02}:00", end=f"{h:02}:50")
                      for h, p in enumerate([*range(1, 10), "a", "b", "c"], 8)]

    def action(self, choice, values):
        inputs = iter(values)
        output = io.StringIO()
        with redirect_stdout(output):
            activity_action(choice, self.activities, {}, self.rooms, self.students,
                            lambda _: next(inputs), period_times=self.clock)
        return output.getvalue()

    def test_full_lifecycle_and_capacity(self):
        self.assertIn("新增成功", self.action("1", ["A1", "講座", "2026-11-18",
                                                "1200", "1300", "2", "講座", "投影機"]))
        for student in ("S0", "S1"):
            self.assertIn("報名成功", self.action("5", ["A1", student]))
        with self.assertRaisesRegex(ValueError, "額滿"):
            self.action("5", ["A1", "S2"])
        self.assertIn("報名：2/2", self.action("4", ["", "S0", ""]))
        self.action("3", ["A1", "新名稱", "", "1300", "1400", "", "", "-"])
        self.assertEqual(self.activities["A1"]["name"], "新名稱")
        self.assertEqual(self.activities["A1"]["participants"], ["S0", "S1"])
        self.assertIn("已取消", self.action("2", ["A1"]))
        self.assertFalse(self.activities)

    def test_room_rejection_explains_requirements(self):
        output = self.action("6", ["A1", "講座", "2026-11-18", "1200", "1300",
                                   "3", "講座", "麥克風"])
        self.assertIn("無合適教室", output)
        self.assertIn("容量 2", output)
        self.assertIn("缺少設備 麥克風", output)
        self.assertFalse(self.activities)

    def test_four_digit_time_and_blank_update(self):
        values = iter(["早晨活動", "2026-11-18", "0800", "0900", "2", "聚會", "-"])
        record = input_activity(lambda _: next(values), "A1")
        self.assertEqual(record["start"], "2026-11-18T08:00+08:00")
        self.assertEqual(record["end"], "2026-11-18T09:00+08:00")
        self.assertEqual(input_activity(lambda _: "", "A1", record), record)
        for invalid in ("800", "08:00", "2400", "0860", "abcd", "０８００"):
            with self.subTest(time=invalid):
                values = iter(["活動", "2026-11-18", invalid])
                with self.assertRaisesRegex(ValueError, "HHMM"):
                    input_activity(lambda _: next(values), "A1")

    def test_menu_recovers_from_invalid_choice(self):
        inputs = iter(["7", "", "4", "", "", "", "", "0"])
        with redirect_stdout(io.StringIO()) as output:
            activity_menu(self.activities, {}, self.rooms, self.students,
                          lambda _: next(inputs), lambda *a, **k: None, [])
        self.assertIn("請輸入合法選項", output.getvalue())
        self.assertIn("查無符合條件", output.getvalue())

    def test_menu_uses_default_clock_without_extra_prompts(self):
        inputs = iter(["1", "A1", "午間活動", "2026-11-18", "1210", "1300",
                       "2", "聚會", "-", "", "0"])
        clock = []
        with redirect_stdout(io.StringIO()):
            activity_menu(self.activities, {}, self.rooms, self.students,
                          lambda _: next(inputs), lambda *a, **k: None, clock)
        self.assertEqual(clock, default_period_times())
        self.assertIn("A1", self.activities)

    def test_actual_clock_respects_lunch_and_adjacent_night_periods(self):
        courses = {"C1": dict(id="C1", name="課程", credits=3, required=False,
                              teacher="T", capacity=2, room="R1",
                              schedule=[[3, 4], [3, "a"], [3, "b"]])}
        clock = default_period_times()

        def create(code, start, end):
            return add_activity(self.activities, courses, self.rooms,
                                dict(id=code, name=code, type="講座", capacity=2,
                                     required_equipment=[], start=f"2026-11-18T{start}+08:00",
                                     end=f"2026-11-18T{end}+08:00"), period_times=clock)

        create("LUNCH", "12:10", "13:00")
        create("BREAK", "20:10", "20:20")
        with self.assertRaisesRegex(ValueError, "課程 C1"):
            create("NIGHT", "19:20", "19:30")
        with self.assertRaisesRegex(ValueError, "課程 C1"):
            create("MORNING", "11:50", "12:10")


if __name__ == "__main__":
    unittest.main()
