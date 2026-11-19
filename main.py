import json
import os
from pathlib import Path

from course import validate_course
from course_crud import course_action


debug_mode = False


def enable_debug():
    global debug_mode
    debug_mode = True
    print("Debug 模式已啟用，可輸入 /stop 結束程式。")


def read_input(prompt):
    value = input(prompt).strip()

    if debug_mode and value == "/stop":
        raise SystemExit(0)
    
    return value


def show_menu(options, current_function=None):
    os.system("cls" if os.name == "nt" else "clear")
    if debug_mode:
        print("Debug 模式已啟用")
    print("------------------------------------------------")
    print("歡迎來到智慧校園課程與活動整合規劃系統(SCCAPS)")
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


def course_management_menu(courses):
    options = ["新增", "刪除", "修改", "查詢"]
    while True:
        show_menu(options, current_function="資料管理系統-課程管理")
        choice = read_input("請輸入選項（0 返回資料管理系統）：")
        if choice == "0":
            return
        if choice in ("1", "2", "3", "4"):
            os.system("cls" if os.name == "nt" else "clear")
            try:
                course_action(choice, courses, read_input)
            except (OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
                print(f"操作失敗：{error}")
            read_input("按 Enter 繼續")
        else:
            invalid_choice()


def data_management_menu(courses):
    options = ["課程管理", "學生管理", "教室管理"]
    while True:
        show_menu(options, current_function="資料管理系統")
        choice = read_input("請輸入選項（0 返回主選單）：")
        if choice == "0":
            return
        if choice == "1":
            course_management_menu(courses)
        elif choice in ("2", "3"):
            os.system("cls" if os.name == "nt" else "clear")
            print(f"{options[int(choice) - 1]}功能尚未開放。")
            read_input("按 Enter 繼續")
        else:
            invalid_choice()
            continue  # 按 Enter 後重新顯示目前的子選單


def main_menu(courses):
    options = ["資料管理系統", "個人課表產生", "智慧課表規劃", "校園活動系統", "校園路徑規劃"]
    while True:
        show_menu(options)
        choice = read_input("請輸入選項（0 離開系統）：")
        if choice == "0":
            return
        if choice == "1":
            data_management_menu(courses)
        elif choice in ("2", "3", "4", "5"):
            os.system("cls" if os.name == "nt" else "clear")
            print("此功能尚未開放。")
            read_input("按 Enter 繼續")
        else:
            invalid_choice()


def load_courses():
    courses = {}
    while True:
        use_json = read_input("是否使用測試資料庫courses.json（y/n）：").lower()
        if use_json == "114514":
            enable_debug()
        elif use_json in ("y", "n"):
            break
        else:
            invalid_choice("不合法的輸入")

    if use_json == "y":
        try:
            with Path(__file__).with_name("courses.json").open(encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, dict):
                raise ValueError("課程資料必須是以課程代碼為鍵的物件")
            for course_id, course in data.items():
                if not validate_course(course) or course_id != course["id"]:
                    raise ValueError("課程資料格式不正確")
            courses = data
            print(f"已載入 {len(courses)} 門課程。")
        except (OSError, UnicodeError, ValueError) as error:
            print(f"無法載入 courses.json：{error}，將使用空的課程資料。")

    return courses


def main():
    courses = load_courses()
    main_menu(courses)


if __name__ == "__main__":
    main()
