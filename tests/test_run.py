from f1_manager import get_data, delete_course, query_courses

# 模擬組員給的假資料
mock_classrooms = ["TR-212", "TR-310", "TR-401", "TR-515", "TR-601"]
mock_courses = [
    {
        "course_id": "CS101",
        "name": "計算機程式設計",
        "credits": 3,
        "is_required": True,
        "instructor": "郭忠義",
        "capacity": 50,
        "classroom": "TR-212",
        "time_slots": [(1, "2"), (1, "3")]
    }
]
mock_students = [
    {
        "student_id": "112590001",
        "name": "王小明",
        "department_grade": "資工二A",
        "max_credits": 25
    }
]

# 測試整合
state = get_data(mock_courses, mock_students, mock_classrooms)
print("整合成功，系統狀態包含課程數：", len(state["courses"]))

# 測試查詢
found = query_courses(state, instructor="郭忠義")
print("查詢結果：", [c["name"] for c in found])