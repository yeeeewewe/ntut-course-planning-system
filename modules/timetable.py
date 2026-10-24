"""F3 純課程建表與格子查詢的私人輔助邏輯。

建立課程格子與學分資料，查詢既有占用；不整合活動原始資料或提供公開入口。
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


def _query_timetable_grid(
    grid, *, day=None, period=None, course_id=None,
) -> list[dict]:
    """依 AND 條件查詢既有格子，回傳獨立的非空格紀錄。

    先驗證全部格子；活動只查詢 kind、id、name 標籤。
    None 表示不篩選，course_id 只匹配課程占用。
    """
    if grid is None:
        raise ValueError("MISSING_DATA: grid 必須明確提供")
    if not isinstance(grid, list) or len(grid) != 7:
        raise ValueError("INVALID_INPUT: grid 必須是七列的 list")
    if day is not None and (type(day) is not int or not 1 <= day <= 7):
        raise ValueError("INVALID_INPUT: day 必須是 1～7 的 int 或 None，不接受 bool")
    if period is not None:
        valid_period = (
            type(period) is int and 1 <= period <= 9
        ) or (
            isinstance(period, str) and period in ("a", "b", "c")
        )
        if not valid_period:
            raise ValueError("INVALID_INPUT: period 必須是 1～9 的 int、a、b、c 或 None")
    if course_id is not None and (
        not isinstance(course_id, str) or not course_id.strip()
    ):
        raise ValueError("INVALID_INPUT: course_id 必須是非空白 str 或 None")

    # 驗證整張 grid，不因查詢條件而略過非法占用。
    for row in grid:
        if not isinstance(row, list) or len(row) != 12:
            raise ValueError("INVALID_INPUT: grid 每列必須是十二格的 list")
        for cell in row:
            if not isinstance(cell, list):
                raise ValueError("INVALID_INPUT: 每格占用必須是 list")
            seen_sources = []
            for item in cell:
                if not isinstance(item, dict):
                    raise ValueError("INVALID_INPUT: 占用項目必須是 dict")
                kind = item.get("kind")
                item_id = item.get("id")
                name = item.get("name")
                if kind not in ("course", "activity"):
                    raise ValueError("INVALID_INPUT: kind 必須是 course 或 activity")
                if not isinstance(item_id, str) or not item_id.strip():
                    raise ValueError("INVALID_INPUT: 占用 id 必須是非空白 str")
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("INVALID_INPUT: 占用 name 必須是非空白 str")
                source = [kind, item_id]
                if source in seen_sources:
                    raise ValueError("INVALID_INPUT: 同格不得重複相同 kind 與 id 的占用")
                seen_sources.append(source)

    results = []
    period_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, "a", "b", "c"]
    for day_index in range(7):
        if day is not None and day_index + 1 != day:
            continue
        for period_index in range(12):
            current_period = period_order[period_index]
            if period is not None and current_period != period:
                continue
            items = []
            for item in grid[day_index][period_index]:
                if course_id is not None and (
                    item["kind"] != "course" or item["id"] != course_id
                ):
                    continue
                items.append({
                    "kind": item["kind"],
                    "id": item["id"],
                    "name": item["name"],
                })
            if items:
                items.sort(key=lambda item: (
                    0 if item["kind"] == "course" else 1,
                    item["id"],
                ))
                results.append({
                    "day": day_index + 1,
                    "period": current_period,
                    "items": items,
                })
    return results
