# f1_manager.py

VALID_WEEKDAYS = {1, 2, 3, 4, 5, 6, 7}
VALID_PERIODS = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c"}

def validate_course(course, available_classrooms):
    """檢查單門課程的資料防呆"""
    # 檢查學分必須為正整數
    if not isinstance(course.get("credits"), int) or course["credits"] < 1:
        raise ValueError(f"學分必須為正整數: {course.get('course_id')}")

    # 檢查人數上限不得小於 1
    if not isinstance(course.get("capacity"), int) or course["capacity"] < 1:
        raise ValueError(f"人數上限不得小於1: {course.get('course_id')}")

    # 檢查時段輸入是否正確 (星期 1-7, 節次 1-9, a, b, c)
    time_slots = course.get("time_slots", [])
    if not time_slots:
        raise ValueError(f"課程必須設定上課時段: {course.get('course_id')}")
        
    for day, period in time_slots:
        if day not in VALID_WEEKDAYS or str(period).lower() not in VALID_PERIODS:
            raise ValueError(f"非法時段設定: 星期{day} 第{period}節 ({course.get('course_id')})")

    # 檢查教室是否在可用教室清單中
    if course.get("classroom") not in available_classrooms:
        raise ValueError(f"無效教室名稱: {course.get('classroom')}")

def validate_student(student):
    """檢查學生資料防呆"""
    if not isinstance(student.get("max_credits"), int) or student["max_credits"] < 1:
        raise ValueError(f"學分上限必須為正整數: {student.get('student_id')}")

def get_data(course_list, student_list, classroom_list):
    """
    整合函式：接收 C1, C2, D 提供的資料，進行驗證並整合成系統狀態物件 (純資料字典)
    """
    state = {
        "classrooms": set(classroom_list),
        "courses": {},
        "students": {}
    }

    # 1. 處理並驗證課程
    for c in course_list:
        cid = c["course_id"]
        # 課程代號不能重複
        if cid in state["courses"]:
            raise ValueError(f"課程代號重複: {cid}")
        
        validate_course(c, state["classrooms"])
        
        # copy並初始化已選學生名冊
        course_record = dict(c)
        course_record.setdefault("enrolled_students", set())
        state["courses"][cid] = course_record

    # 2. 處理並驗證學生
    for s in student_list:
        sid = s["student_id"]
        # 學號不能重複
        if sid in state["students"]:
            raise ValueError(f"學號重複: {sid}")
            
        validate_student(s)
        
        # copy並初始化已選課程清單
        student_record = dict(s)
        student_record.setdefault("enrolled_courses", set())
        state["students"][sid] = student_record

    return state

# --- 增刪改查判斷函式 ---

def delete_course(state, course_id):
    """刪除課程防呆：若有學生選修則拒絕刪除"""
    if course_id not in state["courses"]:
        raise KeyError(f"找不到課程: {course_id}")
    
    course = state["courses"][course_id]
    if len(course["enrolled_students"]) > 0:
        raise RuntimeError(f"課程 {course_id} 已有學生選修，禁止刪除")
    
    del state["courses"][course_id]
    return True

def query_courses(state, course_id=None, instructor=None, weekday=None, is_required=None, has_remaining_seats=None):
    """支援多條件查詢課程"""
    results = []
    for c in state["courses"].values():
        if course_id and c["course_id"] != course_id:
            continue
        if instructor and c["instructor"] != instructor:
            continue
        if weekday and not any(day == weekday for day, _ in c["time_slots"]):
            continue
        if is_required is not None and c["is_required"] != is_required:
            continue
        if has_remaining_seats is True and len(c["enrolled_students"]) >= c["capacity"]:
            continue
        results.append(c)
    return results