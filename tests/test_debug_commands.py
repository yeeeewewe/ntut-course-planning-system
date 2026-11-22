import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import main


class TestDebugCommands(unittest.TestCase):
    def setUp(self):
        self.ui = main.create_input_handler()
        self.enterContext(self.ui.input_context())

    def test_view_all_sources_reads_current_data_and_reprompts(self):
        sources = {name: {} for name in ("student", "classroom", "course", "activity")}
        with redirect_stdout(io.StringIO()):
            self.ui.enable_debug()
        with self.ui.input_context(**sources):
            for name, alias in zip(sources, ("學生", "教室", "課程", "活動")):
                sources[name]["NEW"] = {"name": "最新資料"}
                for command in (name, alias):
                    with self.subTest(command=command), patch("builtins.input", side_effect=[
                        f"/view {command}", "", "next"
                    ]) as reader, patch("main.os.system") as clear_screen, redirect_stdout(io.StringIO()) as output:
                        self.assertEqual(self.ui.read_input("prompt"), "next")
                        self.assertEqual(reader.call_count, 3)
                        self.assertEqual(reader.call_args_list[1].args, ("按 Enter 繼續",))
                        self.assertEqual(clear_screen.call_count, 2)
                        payload = output.getvalue().split("\n", 1)[1]
                        self.assertEqual(json.loads(payload), sources[name])

    def test_invalid_view_commands_keep_waiting(self):
        with redirect_stdout(io.StringIO()):
            self.ui.enable_debug()
        with patch("builtins.input", side_effect=[
            "/view", "/view unknown", "/view student extra", "0"
        ]), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(self.ui.read_input("prompt"), "0")
            self.assertEqual(output.getvalue().count("用法："), 3)

    def test_view_waits_before_redrawing_original_menu(self):
        with patch("main.os.system"), redirect_stdout(io.StringIO()) as output:
            self.ui.enable_debug()
            self.ui.show_menu(["ACTIVITY"], "ACTIVITY_MENU")
            def answer(prompt):
                if prompt == "\u6309 Enter \u7e7c\u7e8c":
                    self.assertEqual(output.getvalue().count("ACTIVITY_MENU"), 1)
                    return ""
                return next(values)
            values = iter(["/view activity", "0"])
            with patch("builtins.input", side_effect=answer):
                self.assertEqual(self.ui.read_input("choice"), "0")
            self.assertEqual(output.getvalue().count("ACTIVITY_MENU"), 2)

    def test_view_is_plain_input_outside_debug(self):
        with patch("builtins.input", return_value="/view student"):
            self.assertEqual(self.ui.read_input("prompt"), "/view student")

    def test_stop_still_exits(self):
        with redirect_stdout(io.StringIO()):
            self.ui.enable_debug()
        with patch("builtins.input", return_value="/stop"):
            with self.assertRaises(SystemExit):
                self.ui.read_input("prompt")

    def test_nested_context_restores_data_and_menu_even_after_error(self):
        outer = {"OUTER": {"name": "original"}}
        with self.ui.input_context(student=outer), patch("main.os.system"), \
                redirect_stdout(io.StringIO()) as output:
            self.ui.enable_debug()
            self.ui.show_menu(["MAIN"], "OUTER_MENU")
            with self.assertRaises(ValueError):
                with self.ui.input_context(student={"INNER": {}}):
                    self.ui.show_menu(["SUB"], "INNER_MENU")
                    raise ValueError("exit")
            outer["NEW"] = {}
            output.seek(0)
            output.truncate(0)
            with patch("builtins.input", side_effect=["/view student", "", "0"]):
                self.assertEqual(self.ui.read_input("choice"), "0")
            text = output.getvalue()
            payload = text[text.index("{"):]
            data, _ = json.JSONDecoder().raw_decode(payload)
            self.assertEqual(data, outer)
            self.assertIn("OUTER_MENU", text)
            self.assertNotIn("INNER_MENU", text)

    def test_handlers_do_not_share_debug_mode(self):
        other = main.create_input_handler()
        with redirect_stdout(io.StringIO()):
            self.ui.enable_debug()
        with patch("builtins.input", return_value="/stop"):
            self.assertEqual(other.read_input("choice"), "/stop")
        for name in ("read_input", "input_context", "remember_menu", "debug_mode"):
            self.assertNotIn(name, vars(main))


if __name__ == "__main__":
    unittest.main()
