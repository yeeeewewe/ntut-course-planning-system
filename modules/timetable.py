"""F3 建表、格子查詢與統計的私人輔助邏輯。

建立課程格子，查詢既有占用與空閒，並計算統計；不整合活動原始資料或提供公開入口。
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


def _validate_timetable_grid(grid) -> None:
    """驗證全部七乘十二格及占用標籤，不修改輸入。"""
    if grid is None:
        raise ValueError("MISSING_DATA: grid 必須明確提供")
    if not isinstance(grid, list) or len(grid) != 7:
        raise ValueError("INVALID_INPUT: grid 必須是七列的 list")

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


def _query_timetable_grid(
    grid, *, day=None, period=None, course_id=None,
) -> list[dict]:
    """依 AND 條件查詢既有格子，回傳獨立的非空格紀錄。

    先驗證全部格子；活動只查詢 kind、id、name 標籤。
    None 表示不篩選，course_id 只匹配課程占用。
    """
    _validate_timetable_grid(grid)
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


def _find_free_grid_periods(grid, *, start, end, min_periods=3) -> list[dict]:
    """列出含兩端的查詢範圍內，各日符合長度的最大空閒區段。"""
    if grid is None or start is None or end is None:
        raise ValueError("MISSING_DATA: grid、start 與 end 必須明確提供")
    _validate_timetable_grid(grid)
    if type(min_periods) is not int or min_periods < 1:
        raise ValueError("INVALID_INPUT: min_periods 必須是正整數，不接受 bool")

    period_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, "a", "b", "c"]
    for slot in [start, end]:
        if not isinstance(slot, list) or len(slot) != 2:
            raise ValueError("INVALID_INPUT: start 與 end 必須是 [day, period] 的 list")
        day, period = slot
        if type(day) is not int or not 1 <= day <= 7:
            raise ValueError("INVALID_INPUT: 端點星期必須是 1～7 的 int，不接受 bool")
        valid_period = (
            type(period) is int and 1 <= period <= 9
        ) or (
            isinstance(period, str) and period in ("a", "b", "c")
        )
        if not valid_period:
            raise ValueError("INVALID_INPUT: 端點節次必須是 1～9 的 int 或 a、b、c")

    start_day, start_period = start
    end_day, end_period = end
    start_index = period_order.index(start_period)
    end_index = period_order.index(end_period)
    if start_day > end_day or (start_day == end_day and start_index > end_index):
        raise ValueError("INVALID_INPUT: start 不得晚於 end")

    results = []
    for day_index in range(start_day - 1, end_day):
        first_period = 0
        last_period = 11
        if day_index == start_day - 1:
            first_period = start_index
        if day_index == end_day - 1:
            last_period = end_index

        free_periods = []
        for period_index in range(first_period, last_period + 1):
            if not grid[day_index][period_index]:
                free_periods.append(period_order[period_index])
            else:
                if len(free_periods) >= min_periods:
                    results.append({"day": day_index + 1, "periods": free_periods})
                free_periods = []
        # 當日或查詢範圍末端也可能仍在空閒區段中。
        if len(free_periods) >= min_periods:
            results.append({"day": day_index + 1, "periods": free_periods})
    return results


def _summarize_timetable_grid(grid, course_credits) -> dict:
    """統計上課格數、每週學分、首末占用間空堂及全部空白格數。"""
    if grid is None or course_credits is None:
        raise ValueError("MISSING_DATA: grid 與 course_credits 必須明確提供")
    _validate_timetable_grid(grid)
    if not isinstance(course_credits, dict):
        raise ValueError("INVALID_INPUT: course_credits 必須是 dict")

    weekly_credits = 0
    for course_id, credits in course_credits.items():
        if not isinstance(course_id, str) or not course_id.strip():
            raise ValueError("INVALID_INPUT: 學分對照的課程代號必須是非空白 str")
        if type(credits) is not int or credits < 1:
            raise ValueError("INVALID_INPUT: 課程學分必須是正整數，不接受 bool")
        weekly_credits += credits

    grid_course_ids = []
    daily_class_periods = []
    daily_gaps = []
    empty_periods = 0
    for row in grid:
        class_periods = 0
        first_occupied = None
        last_occupied = None
        for period_index in range(12):
            cell = row[period_index]
            if not cell:
                empty_periods += 1
                continue
            if first_occupied is None:
                first_occupied = period_index
            last_occupied = period_index

            has_course = False
            for item in cell:
                if item["kind"] == "course":
                    has_course = True
                    if item["id"] not in grid_course_ids:
                        grid_course_ids.append(item["id"])
            if has_course:
                class_periods += 1

        gaps = 0
        if first_occupied is not None:
            for period_index in range(first_occupied + 1, last_occupied):
                if not row[period_index]:
                    gaps += 1
        daily_class_periods.append(class_periods)
        daily_gaps.append(gaps)

    # 學分對照須恰好涵蓋所有不同課程，活動不需要學分。
    if len(course_credits) != len(grid_course_ids):
        raise ValueError("INVALID_INPUT: course_credits 必須與 grid 的課程代號一致")
    for course_id in grid_course_ids:
        if course_id not in course_credits:
            raise ValueError("INVALID_INPUT: course_credits 必須與 grid 的課程代號一致")

    return {
        "daily_class_periods": daily_class_periods,
        "weekly_credits": weekly_credits,
        "daily_gaps": daily_gaps,
        "total_gaps": sum(daily_gaps),
        "empty_periods": empty_periods,
    }
