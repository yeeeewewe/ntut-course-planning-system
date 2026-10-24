"""F2 純課程時間、候選學分與名額的私人輔助邏輯。

沿用 F1 課程與學生資料，所有輸入維持不變。
尚未提供完整 F2 公開入口；不處理活動。
"""


def _find_course_overlaps(courses, course_ids) -> list[dict]:
    """找出指定課程全部共同節次，供學生及教室檢查共用。

    只驗證集合、指定代號、id 對應及 schedule；不驗證無關欄位。
    回傳獨立紀錄，由呼叫者補上問題種類與教室。
    """
    if courses is None or course_ids is None:
        raise ValueError("MISSING_DATA: courses 與 course_ids 必須明確提供")
    if not isinstance(courses, dict) or not isinstance(course_ids, list):
        raise ValueError("INVALID_INPUT: courses 必須是 dict，course_ids 必須是 list")

    seen_course_ids = []
    for course_id in course_ids:
        if not isinstance(course_id, str) or not course_id.strip():
            raise ValueError("INVALID_INPUT: 課程代號必須是非空白 str")
        if course_id in seen_course_ids:
            raise ValueError("INVALID_INPUT: 候選課程代號不得重複")
        if course_id not in courses:
            raise ValueError("INVALID_INPUT: 課程代號必須參照 courses 中的課程")
        seen_course_ids.append(course_id)

        course = courses[course_id]
        if course is None:
            raise ValueError("MISSING_DATA: 指定課程資料不可為 None")
        if not isinstance(course, dict) or course.get("id") != course_id:
            raise ValueError("INVALID_INPUT: 課程必須是 dict，且 id 與集合鍵一致")
        if "schedule" not in course:
            raise ValueError("INVALID_INPUT: 課程缺少 schedule 欄位")
        schedule = course["schedule"]
        if schedule is None:
            raise ValueError("MISSING_DATA: 課程 schedule 不可為 None")
        if not isinstance(schedule, list) or not schedule:
            raise ValueError("INVALID_INPUT: 課程 schedule 必須是非空 list")

        seen_slots = []
        for slot in schedule:
            if not isinstance(slot, list) or len(slot) != 2:
                raise ValueError("INVALID_INPUT: 每個時段必須是 [day, period] 的 list")
            day, period = slot
            if type(day) is not int or not 1 <= day <= 7:
                raise ValueError("INVALID_INPUT: 星期必須是 1～7 的 int，不接受 bool")
            valid_period = (
                type(period) is int and 1 <= period <= 9
            ) or (
                isinstance(period, str) and period in ("a", "b", "c")
            )
            if not valid_period:
                raise ValueError("INVALID_INPUT: 節次必須是 1～9 的 int 或 a、b、c")
            if slot in seen_slots:
                raise ValueError("INVALID_INPUT: 同一課程的 schedule 不得重複時段")
            seen_slots.append(slot)

    ordered_course_ids = sorted(course_ids)
    results = []
    # 只比較後面的課程，避免自身配對及反向重複。
    for first_index in range(len(ordered_course_ids)):
        first_id = ordered_course_ids[first_index]
        for second_index in range(first_index + 1, len(ordered_course_ids)):
            second_id = ordered_course_ids[second_index]
            for first_slot in courses[first_id]["schedule"]:
                for second_slot in courses[second_id]["schedule"]:
                    if first_slot == second_slot:
                        results.append({
                            "course_ids": [first_id, second_id],
                            "activity_ids": [],
                            "day": first_slot[0],
                            "periods": [first_slot[1]],
                            "start": None,
                            "end": None,
                        })

    period_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, "a", "b", "c"]
    results.sort(key=lambda issue: (
        issue["day"],
        period_order.index(issue["periods"][0]),
        issue["course_ids"][0],
        issue["course_ids"][1],
    ))
    return results


def _find_student_course_conflicts(courses, candidate_course_ids) -> list[dict]:
    """檢查整份候選選課清單，回傳全部 student_time 課程衝堂。

    candidate_course_ids 是不重複的課程代號 list；[] 表示明確沒有選課。
    不需要學生其他欄位、教室資料、日期或鐘點表。
    """
    results = _find_course_overlaps(courses, candidate_course_ids)
    for issue in results:
        issue["type"] = "student_time"
        issue["room"] = None
    return results


def _find_course_room_conflicts(courses) -> list[dict]:
    """檢查整個課程集合，回傳全部同教室的 room_time 衝突。

    每門課程的 room 須為 F1 非空白 str；不檢查教室存在性或容量設備。
    """
    if courses is None:
        raise ValueError("MISSING_DATA: courses 必須明確提供")
    if not isinstance(courses, dict):
        raise ValueError("INVALID_INPUT: courses 必須是 dict")

    overlaps = _find_course_overlaps(courses, list(courses))
    for course in courses.values():
        room = course.get("room")
        if room is None:
            raise ValueError("MISSING_DATA: 課程教室資訊必須明確提供")
        if not isinstance(room, str) or not room.strip():
            raise ValueError("INVALID_INPUT: room 必須是非空白 str")

    results = []
    for issue in overlaps:
        first_id, second_id = issue["course_ids"]
        room = courses[first_id]["room"]
        if room != courses[second_id]["room"]:
            continue
        issue["type"] = "room_time"
        issue["room"] = room
        results.append(issue)
    return results


def _check_student_credit_capacity(
    courses, students, candidate_student, *, existing_student_id=None,
) -> dict:
    """計算候選學生的 credits 與學分、課程名額 issues，不修改輸入。

    資料須遵照 F1；此處只驗證本次計算依賴的欄位。
    existing_student_id=None 為新增，否則以候選完整選課取代原學生。
    """
    if courses is None or students is None or candidate_student is None:
        raise ValueError("MISSING_DATA: courses、students 與 candidate_student 必須明確提供")
    if (
        not isinstance(courses, dict)
        or not isinstance(students, dict)
        or not isinstance(candidate_student, dict)
    ):
        raise ValueError("INVALID_INPUT: courses、students 與 candidate_student 必須是 dict")

    candidate_id = candidate_student.get("id")
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ValueError("INVALID_INPUT: 候選學生 id 必須是非空白 str")
    credit_limit = candidate_student.get("credit_limit")
    if type(credit_limit) is not int or credit_limit < 1:
        raise ValueError("INVALID_INPUT: credit_limit 必須是正整數，不接受 bool")

    if existing_student_id is None:
        if candidate_id in students:
            raise ValueError("INVALID_INPUT: 新增學生的 id 不得已存在")
    else:
        if not isinstance(existing_student_id, str) or not existing_student_id.strip():
            raise ValueError("INVALID_INPUT: existing_student_id 必須是非空白 str 或 None")
        if existing_student_id != candidate_id:
            raise ValueError("INVALID_INPUT: 修改學生不得變更 id")
        if existing_student_id not in students:
            raise ValueError("INVALID_INPUT: 原學生必須存在")

    # 現有人數與候選學分都依賴有效且不重複的選課參照。
    student_records = list(students.items())
    student_records.append((candidate_id, candidate_student))
    for student_id, student in student_records:
        if not isinstance(student_id, str) or not student_id.strip():
            raise ValueError("INVALID_INPUT: 學生集合鍵必須是非空白 str")
        if not isinstance(student, dict) or student.get("id") != student_id:
            raise ValueError("INVALID_INPUT: 學生必須是 dict，且 id 與集合鍵一致")
        enrolled_courses = student.get("enrolled_courses")
        if not isinstance(enrolled_courses, list):
            raise ValueError("INVALID_INPUT: enrolled_courses 必須是 list")
        seen_course_ids = []
        for course_id in enrolled_courses:
            if not isinstance(course_id, str) or not course_id.strip():
                raise ValueError("INVALID_INPUT: 選課代號必須是非空白 str")
            if course_id in seen_course_ids:
                raise ValueError("INVALID_INPUT: enrolled_courses 不得重複課程代號")
            if course_id not in courses:
                raise ValueError("INVALID_INPUT: 選課代號必須參照 courses 中的課程")
            course = courses[course_id]
            if not isinstance(course, dict) or course.get("id") != course_id:
                raise ValueError("INVALID_INPUT: 課程必須是 dict，且 id 與集合鍵一致")
            seen_course_ids.append(course_id)

    before = 0
    if existing_student_id is not None:
        for course_id in students[existing_student_id]["enrolled_courses"]:
            credits = courses[course_id].get("credits")
            if type(credits) is not int or credits < 1:
                raise ValueError("INVALID_INPUT: 課程 credits 必須是正整數，不接受 bool")
            before += credits

    candidate_course_ids = candidate_student["enrolled_courses"]
    after = 0
    for course_id in candidate_course_ids:
        credits = courses[course_id].get("credits")
        capacity = courses[course_id].get("capacity")
        if type(credits) is not int or credits < 1:
            raise ValueError("INVALID_INPUT: 課程 credits 必須是正整數，不接受 bool")
        if type(capacity) is not int or capacity < 1:
            raise ValueError("INVALID_INPUT: 課程 capacity 必須是正整數，不接受 bool")
        after += credits

    issues = []
    if after > credit_limit:
        issues.append({"type": "credit_limit"})

    # 先排除原學生，再加入候選學生一次，保留原課時不會重複計人。
    for course_id in sorted(candidate_course_ids):
        enrolled = 0
        for student_id, student in students.items():
            if student_id == existing_student_id:
                continue
            if course_id in student["enrolled_courses"]:
                enrolled += 1
        enrolled += 1
        capacity = courses[course_id]["capacity"]
        if enrolled > capacity:
            issues.append({
                "type": "capacity",
                "course_id": course_id,
                "enrolled": enrolled,
                "capacity": capacity,
            })

    return {
        "credits": {"before": before, "after": after, "limit": credit_limit},
        "issues": issues,
    }
