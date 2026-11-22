"""學生管理的互動操作介面；資料只更新於記憶體。"""

import json
from datetime import date, timedelta

from .conflict import check_student_state
from .student import add_student, delete_student, search_student, update_student, validate_student


def input_student_fields(read_input):
    name = read_input("學生姓名：")
    department = read_input("系級：")
    credit_limit = int(read_input("學分上限："))
    enrolled = read_input("已選課程代碼（以逗號分隔，留空表示未選課）：")
    return {
        "name": name,
        "department": department,
        "credit_limit": credit_limit,
        "enrolled_courses": [code.strip() for code in enrolled.split(",")] if enrolled else [],
    }


def check_student_selection(students, student, courses, *, existing_student_id=None):
    if not validate_student(student, courses):
        raise ValueError("學生資料不合法：請確認必填欄位、正整數學分上限及課程代碼，選課不可重複")
    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    result = check_student_state(
        courses, students, student, [], [], week_start=week_start,
        existing_student_id=existing_student_id,
    )
    if result["issues"]:
        raise ValueError("選課不可行：" + json.dumps(result["issues"], ensure_ascii=False))


def student_action(choice, students, courses, read_input):
    if choice == "1":
        student_id = read_input("學號：")
        if student_id in students:
            raise ValueError("新增失敗：學號重複")
        student = dict(input_student_fields(read_input), id=student_id)
        check_student_selection(students, student, courses)
        if not add_student(students, student, courses):
            raise ValueError("新增失敗：學生資料不合法")
        print("新增成功！")
    elif choice == "2":
        student_id = read_input("要刪除的學號：")
        if student_id not in students:
            raise ValueError("刪除失敗：學生不存在")
        student = students[student_id]
        print("要刪除的學生資料：")
        print("------------------------------------------------")
        print(f"學號：{student['id']}")
        print(f"學生姓名：{student['name']}")
        print(f"系級：{student['department']}")
        print(f"學分上限：{student['credit_limit']}")
        print("已選課程：" + ("、".join(student["enrolled_courses"]) or "未選課"))
        if not delete_student(students, student_id):
            raise ValueError("刪除失敗：學生不存在或學號不合法")
        print("刪除成功！")
    elif choice == "3":
        student_id = read_input("要修改的學號：")
        if student_id not in students:
            raise ValueError("學生不存在")
        print("請重新輸入學生資料（學號不變）：")
        changes = input_student_fields(read_input)
        check_student_selection(students, dict(changes, id=student_id), courses,
                                existing_student_id=student_id)
        if not update_student(students, student_id, changes, courses):
            raise ValueError("修改失敗：學生資料不合法")
        print("修改成功！")
    elif choice == "4":
        student_id = read_input("學號（留空查詢全部）：") or None
        results = search_student(students, student_id=student_id)
        if not results:
            print("查無符合條件的學生。")
        for student in results:
            print(json.dumps(student, ensure_ascii=False, indent=2))
