import json
from pathlib import Path

from course import add_course, delete_course, search_course, update_course


def read_json(filename):
    with Path(__file__).with_name(filename).open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{filename} 必須是 JSON 物件")
    return data


def input_course_fields(read_input):
    name = read_input("課程名稱：")
    credits = int(read_input("學分數："))
    required = read_input("是否必修（y/n）：").lower()
    if required not in ("y", "n"):
        raise ValueError("是否必修請輸入 y 或 n")
    teacher = read_input("授課教師：")
    capacity = int(read_input("人數上限："))
    room = read_input("上課教室：")
    day = int(read_input("上課星期（1～7）："))
    period = read_input("上課節次（1～9 或 a、b、c）：").lower()
    if period.isdigit():
        period = int(period)

    return {
        "name": name,
        "credits": credits,
        "required": required == "y",
        "teacher": teacher,
        "capacity": capacity,
        "room": room,
        "schedule": [[day, period]],
    }


def check_course_room(course):
    rooms = read_json("classrooms.json")
    if course["room"] not in rooms:
        raise ValueError("教室不存在，請使用 classrooms.json 中的教室代碼")


def course_action(choice, courses, read_input):
    if choice == "1":
        course_id = read_input("課程代碼：")
        new_course = input_course_fields(read_input)
        new_course["id"] = course_id
        check_course_room(new_course)
        if not add_course(courses, new_course):
            raise ValueError("新增失敗：課程代碼重複或課程資料不合法")
        print("新增成功！")
    elif choice == "2":
        course_id = read_input("要刪除的課程代碼：")
        students = read_json("students.json")
        if not delete_course(courses, course_id, students):
            raise ValueError("刪除失敗：課程不存在、仍有學生選修或學生資料不合法")
        print("刪除成功！")
    elif choice == "3":
        course_id = read_input("要修改的課程代碼：")
        if course_id not in courses:
            raise ValueError("課程不存在")
        print("請重新輸入課程資料（課程代碼不變）：")
        changes = input_course_fields(read_input)
        check_course_room(changes)
        if not update_course(courses, course_id, changes):
            raise ValueError("修改失敗：課程資料不合法")
        print("修改成功！")
    elif choice == "4":
        course_id = read_input("課程代碼（留空查詢全部）：")
        if course_id == "":
            course_id = None
        students = read_json("students.json")
        results = search_course(courses, students, course_id=course_id)
        if not results:
            print("查無符合條件的課程。")
        for course in results:
            print(json.dumps(course, ensure_ascii=False, indent=2))


