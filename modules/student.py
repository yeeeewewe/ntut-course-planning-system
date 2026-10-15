"""F1 學生資料管理核心函式。

資料格式與對外契約分別見 data_model.docx、function_interface.docx。
選課可行性由呼叫端確認；本模組不讀寫 JSON。
"""

from copy import deepcopy as _deepcopy


def validate_student(student, courses) -> bool:
    """檢查學生模型與課程參照，合法為 True，否則 False，不修改輸入。

    courses 須為符合模型的課程集合；本函式不檢查學生集合內學號
    重複，也不檢查衝堂、總學分、容量或其他選課可行性。
    """
    if not isinstance(student, dict) or not isinstance(courses, dict):
        return False

    required_fields = {
        "id", "name", "department", "enrolled_courses", "credit_limit",
    }
    if student.keys() != required_fields:
        return False

    for field in ("id", "name", "department"):
        value = student[field]
        if not isinstance(value, str) or not value.strip():
            return False

    credit_limit = student["credit_limit"]
    if type(credit_limit) is not int or credit_limit < 1:
        return False

    enrolled_courses = student["enrolled_courses"]
    if not isinstance(enrolled_courses, list):
        return False

    seen_courses = set()
    for course_id in enrolled_courses:
        if not isinstance(course_id, str) or not course_id.strip():
            return False
        if course_id in seen_courses or course_id not in courses:
            return False
        seen_courses.add(course_id)

    return True


def add_student(students, new_student, courses) -> bool:
    """新增合法且學號未重複的學生，成功為 True，一般失敗為 False。

    兩集合須符合模型；呼叫端須完成候選完整學生狀態的必要外部
    檢查，選課清單可非空。只新增學生，失敗時所有輸入維持原狀。
    """
    if not isinstance(students, dict) or not validate_student(new_student, courses):
        return False

    # 目標若與其他輸入共用同一字典，便無法保證其他輸入不變。
    if students is new_student or students is courses:
        return False

    student_id = new_student["id"]
    if student_id in students:
        return False

    stored_student = _deepcopy(new_student)
    students[student_id] = stored_student
    return True
