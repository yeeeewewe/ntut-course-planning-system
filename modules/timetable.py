"""F3 純課程建表的私人輔助邏輯。

只建立課程格子與學分資料，不處理活動或完整公開課表。
所有輸入維持不變，回傳資料獨立建立。
"""


def _build_course_timetable(courses, course_ids) -> dict:
    """將指定課程的全部時段入格，回傳 grid 與 course_credits。

    course_ids 是不重複的課程代號 list，允許 []。
    只驗證建表使用的欄位，不檢查衝堂、學分上限或課程名額。
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
            raise ValueError("INVALID_INPUT: course_ids 不得重複課程代號")
        if course_id not in courses:
            raise ValueError("INVALID_INPUT: 課程代號必須參照 courses 中的課程")
        seen_course_ids.append(course_id)

    # 每次迴圈建立新清單，避免不同列或格子共用可變資料。
    grid = []
    for day_index in range(7):
        row = []
        for period_index in range(12):
            row.append([])
        grid.append(row)
    course_credits = {}
    period_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, "a", "b", "c"]

    # sorted 建立新清單，讓每格的課程依原字串代號排序。
    for course_id in sorted(course_ids):
        course = courses[course_id]
        if course is None:
            raise ValueError("MISSING_DATA: 指定課程資料不可為 None")
        if not isinstance(course, dict) or course.get("id") != course_id:
            raise ValueError("INVALID_INPUT: 課程必須是 dict，且 id 與集合鍵一致")
        name = course.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("INVALID_INPUT: 課程 name 必須是非空白 str")
        credits = course.get("credits")
        if type(credits) is not int or credits < 1:
            raise ValueError("INVALID_INPUT: 課程 credits 必須是正整數，不接受 bool")
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

            period_index = period_order.index(period)
            grid[day - 1][period_index].append({
                "kind": "course",
                "id": course_id,
                "name": name,
            })
        course_credits[course_id] = credits

    return {"grid": grid, "course_credits": course_credits}
