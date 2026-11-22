import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from modules.course import validate_course
from modules.course_crud import course_action
from modules.student import validate_student
from modules.student_crud import student_action
from modules.timetable_ui import timetable_menu
from modules.activity_ui import activity_menu


def create_input_handler():
    """閉包保存暫存堆疊，離開 with 時自動恢復上一層。"""
    debug_mode = False


    def enable_debug():
        nonlocal debug_mode
        debug_mode = True
        print("Debug 模式已啟用，可輸入 /stop 結束程式，或 /view student|classroom|course|activity 查看資料。")


    stack = []

    @contextmanager
    def input_context(**sources):
        data = dict(stack[-1]["data"]) if stack else {
            name: {} for name in ("student", "classroom", "course", "activity")
        }
        data.update(sources)
        frame = {"data": data, "menu": None}
        stack.append(frame)
        try:
            yield
        finally:
            stack.pop()

    def remember_menu(options, current_function):
        if stack:
            stack[-1]["menu"] = (list(options), current_function)

    def read_input(prompt):
        aliases = {"學生": "student", "教室": "classroom", "課程": "course", "活動": "activity"}
        while True:
            value = input(prompt).strip()
            if debug_mode:
                if value == "/stop":
                    raise SystemExit(0)
                parts = value.split()
                if parts and parts[0] == "/view":
                    frame = stack[-1] if stack else {"data": {}, "menu": None}
                    debug_data = frame["data"]
                    last_menu = frame["menu"]
                    name = aliases.get(parts[1], parts[1]) if len(parts) == 2 else None
                    if name not in debug_data:
                        print("用法：/view student|classroom|course|activity（或學生、教室、課程、活動）")
                    else:
                        os.system("cls" if os.name == "nt" else "clear")
                        print(f"目前 {name} 資料（共 {len(debug_data[name])} 筆）：")
                        print(json.dumps(debug_data[name], ensure_ascii=False, indent=2))
                        input("按 Enter 繼續")
                        if last_menu is not None:
                            show_menu(*last_menu)
                        else:
                            os.system("cls" if os.name == "nt" else "clear")
                    continue
            return value


    def show_menu(options, current_function=None):
        remember_menu(options, current_function)
        os.system("cls" if os.name == "nt" else "clear")
        if debug_mode:
            print("Debug 模式已啟用")
        print("------------------------------------------------")
        print("歡迎來到智慧校園課程與活動整合規劃系統(SCCAPS)")
        print(f"目前日期：{datetime.now(timezone(timedelta(hours=8))):%Y-%m-%d}")
        if current_function:
            print(f"當前功能：{current_function}")
        print("請選擇功能：")
        for number, name in enumerate(options, start=1):
            print(f"{number}.{name}")
        print("------------------------------------------------")


    def invalid_choice(message="不合法的輸入，請輸入選項代碼以使用功能。"):
        os.system("cls" if os.name == "nt" else "clear")
        print(message)
        read_input("按 Enter 繼續")


    @input_context()
    def course_management_menu(courses, students):
        options = ["新增", "刪除", "修改", "查詢"]
        while True:
            show_menu(options, current_function="資料管理系統-課程管理")
            choice = read_input("請輸入選項（0 返回資料管理系統）：")
            if choice == "0":
                return
            if choice in ("1", "2", "3", "4"):
                os.system("cls" if os.name == "nt" else "clear")
                try:
                    course_action(choice, courses, read_input, students=students)
                except (OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
                    print(f"操作失敗：{error}")
                read_input("按 Enter 繼續")
            else:
                invalid_choice()


    @input_context()
    def student_management_menu(students, courses):
        options = ["新增", "刪除", "修改", "查詢"]
        while True:
            show_menu(options, current_function="資料管理系統-學生管理")
            choice = read_input("請輸入選項（0 返回資料管理系統）：")
            if choice == "0":
                return
            if choice in ("1", "2", "3", "4"):
                os.system("cls" if os.name == "nt" else "clear")
                try:
                    student_action(choice, students, courses, read_input)
                except (OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
                    print(f"操作失敗：{error}")
                read_input("按 Enter 繼續")
            else:
                invalid_choice()


    @input_context()
    def data_management_menu(courses, students):
        options = ["課程管理", "學生管理", "教室管理"]
        while True:
            show_menu(options, current_function="資料管理系統")
            choice = read_input("請輸入選項（0 返回主選單）：")
            if choice == "0":
                return
            if choice == "1":
                course_management_menu(courses, students)
            elif choice == "2":
                student_management_menu(students, courses)
            elif choice == "3":
                os.system("cls" if os.name == "nt" else "clear")
                print(f"{options[int(choice) - 1]}功能尚未開放。")
                read_input("按 Enter 繼續")
            else:
                invalid_choice()
                continue  # 按 Enter 後重新顯示目前的子選單


    def main_menu(courses, students):
        activities, period_times = {}, []
        classrooms = load_classrooms()
        with input_context(student=students, classroom=classrooms, course=courses, activity=activities):
            options = ["資料管理系統", "個人課表產生", "智慧課表規劃", "校園活動系統", "校園路徑規劃"]
            while True:
                show_menu(options)
                choice = read_input("請輸入選項（0 離開系統）：")
                if choice == "0":
                    return
                if choice == "1":
                    data_management_menu(courses, students)
                elif choice == "2":
                    try:
                        with input_context():
                            timetable_menu(courses, students, read_input, show_menu)
                    except (ValueError, TypeError, KeyError) as error:
                        print(f"操作失敗：{error}")
                        read_input("按 Enter 繼續")
                elif choice == "4":
                    with input_context():
                        activity_menu(activities, courses, classrooms, students, read_input, show_menu, period_times)
                elif choice in ("3", "5"):
                    os.system("cls" if os.name == "nt" else "clear")
                    print("此功能尚未開放。")
                    read_input("按 Enter 繼續")
                else:
                    invalid_choice()


    @input_context()
    def load_data():
        while True:
            use_json = read_input("是否載入測試資料（courses.json、students.json）（y/n）：").lower()
            if use_json == "114514":
                enable_debug()
            elif use_json in ("y", "n"):
                break
            else:
                invalid_choice("不合法的輸入")

        if use_json == "n":
            courses, students = {}, {}
            return courses, students
        courses = load_courses()
        students = load_students(courses)
        print(f"已載入 {len(courses)} 門課程、{len(students)} 個學生資料。")
        with input_context(course=courses, student=students):
            read_input("資料載入完成，按 Enter 繼續")
        return courses, students


    return SimpleNamespace(read_input=read_input, input_context=input_context,
                           show_menu=show_menu, enable_debug=enable_debug,
                           load_data=load_data, main_menu=main_menu)


def load_courses():
    courses = {}
    try:
        with (Path(__file__).parent / "data" / "courses.json").open(encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("課程資料必須是以課程代碼為鍵的物件")
        for course_id, course in data.items():
            if not validate_course(course) or course_id != course["id"]:
                raise ValueError("課程資料格式不正確")
        courses = data
    except (OSError, UnicodeError, ValueError) as error:
        print(f"無法載入 courses.json：{error}，將使用空的課程資料。")

    return courses


def load_students(courses):
    try:
        with (Path(__file__).parent / "data" / "students.json").open(encoding="utf-8") as file:
            students = json.load(file)
        if not isinstance(students, dict) or any(
            not validate_student(student, courses) or student_id != student["id"]
            for student_id, student in students.items()
        ):
            raise ValueError("學生資料格式不正確，或選課代碼不存在於目前課程資料")
        return students
    except (OSError, UnicodeError, ValueError) as error:
        print(f"無法載入 students.json：{error}，將使用空的學生資料。")
        return {}


def load_classrooms():
    try:
        with (Path(__file__).parent / "data" / "classrooms.json").open(encoding="utf-8") as file:
            classrooms = json.load(file)
        if not isinstance(classrooms, dict):
            raise ValueError("教室資料必須是以教室代號為鍵的物件")
        for room_id, room in classrooms.items():
            if (not isinstance(room_id, str) or not room_id.strip()
                    or not isinstance(room, dict) or room.get("id") != room_id
                    or type(room.get("capacity")) is not int or room["capacity"] < 1):
                raise ValueError("教室代號或容量不正確")
            equipment = room.get("equipment", [])
            if (not isinstance(equipment, list)
                    or any(not isinstance(item, str) or not item.strip() for item in equipment)
                    or len(set(equipment)) != len(equipment)):
                raise ValueError("教室設備必須是不重複的非空白文字清單")
        return classrooms
    except (OSError, UnicodeError, ValueError) as error:
        print(f"無法載入 classrooms.json：{error}，將使用空的教室資料。")
        return {}


def main():
    os.system("cls" if os.name == "nt" else "clear")
    ui = create_input_handler()
    courses, students = ui.load_data()
    ui.main_menu(courses, students)


if __name__ == "__main__":
    main()
