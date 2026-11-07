"""F2 學生狀態、活動參與及教室時間檢查。

沿用 F1 課程與學生資料，活動及鐘點由參數提供，所有輸入維持不變。
活動與教室對接格式仍待相關負責人採用。
"""

from datetime import date as _date, datetime as _datetime, timedelta as _timedelta

from .course import validate_course as _validate_course
from .student import validate_student as _validate_student


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


def _parse_week_start(week_start) -> _date:
    """確認嚴格日期、星期一及可表示的下一週一。"""
    if week_start is None:
        raise ValueError("MISSING_DATA: week_start 必須明確提供")
    if not isinstance(week_start, str):
        raise ValueError("INVALID_INPUT: week_start 必須是 YYYY-MM-DD 字串")
    try:
        week = _date.fromisoformat(week_start)
        week + _timedelta(days=7)
    except (ValueError, OverflowError):
        raise ValueError("INVALID_INPUT: week_start 必須是可表示下一週的有效日期") from None
    if week.isoformat() != week_start or week.weekday() != 0:
        raise ValueError("INVALID_INPUT: week_start 必須是嚴格 YYYY-MM-DD 的星期一")
    return week


def _validate_courses(courses) -> None:
    """重用 F1 驗證完整課程集合，未知教室另外依 F2/F3 分類。"""
    if courses is None:
        raise ValueError("MISSING_DATA: courses 必須明確提供")
    if not isinstance(courses, dict):
        raise ValueError("INVALID_INPUT: courses 必須是 dict")
    for course_id, course in courses.items():
        if not isinstance(course_id, str) or not course_id.strip():
            raise ValueError("INVALID_INPUT: 課程集合鍵必須是非空白 str")
        if course is None:
            raise ValueError("MISSING_DATA: 課程資料不可為 None")
        if not isinstance(course, dict) or course.get("id") != course_id:
            raise ValueError("INVALID_INPUT: 課程 id 必須與集合鍵一致")
        if course.get("room") is None:
            raise ValueError("MISSING_DATA: 課程教室資訊必須明確提供")
        if "schedule" in course and course["schedule"] is None:
            raise ValueError("MISSING_DATA: 課程 schedule 不可為 None")
        if not _validate_course(course):
            raise ValueError("INVALID_INPUT: 課程必須符合 F1 八欄模型")


def _parse_period_times(period_times) -> list[list[int]]:
    """將完整十二節鐘點轉為分鐘區間，不預設學校鐘點。"""
    if period_times is None:
        raise ValueError("MISSING_DATA: 活動時間處理需要完整 period_times")
    if not isinstance(period_times, list):
        raise ValueError("INVALID_INPUT: period_times 必須是 list")
    if len(period_times) < 12:
        raise ValueError("MISSING_DATA: period_times 缺少必要節次")
    if len(period_times) > 12:
        raise ValueError("INVALID_INPUT: period_times 必須恰有十二筆")

    period_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, "a", "b", "c"]
    intervals = []
    for index, item in enumerate(period_times):
        if item is None:
            raise ValueError("MISSING_DATA: 節次鐘點不可為 None")
        if not isinstance(item, dict):
            raise ValueError("INVALID_INPUT: 每筆節次鐘點必須是 dict")
        for field in ("period", "start", "end"):
            if field not in item or item[field] is None:
                raise ValueError("MISSING_DATA: 節次鐘點缺少必要欄位")
        expected_period = period_order[index]
        if type(item["period"]) is not type(expected_period) or item["period"] != expected_period:
            raise ValueError("INVALID_INPUT: period_times 須依 1～9、a、b、c 排列")

        minutes = []
        for field in ("start", "end"):
            value = item[field]
            if not isinstance(value, str):
                raise ValueError("INVALID_INPUT: 節次鐘點必須是 HH:MM 字串")
            try:
                clock = _datetime.strptime(value, "%H:%M")
            except ValueError:
                raise ValueError("INVALID_INPUT: 節次鐘點必須是有效 HH:MM") from None
            if clock.strftime("%H:%M") != value:
                raise ValueError("INVALID_INPUT: 節次鐘點必須是嚴格 HH:MM")
            minutes.append(clock.hour * 60 + clock.minute)
        if minutes[0] >= minutes[1]:
            raise ValueError("INVALID_INPUT: 每節 start 必須早於 end，且在同日內")
        if intervals and minutes[0] < intervals[-1][1]:
            raise ValueError("INVALID_INPUT: 節次鐘點須依序且不得重疊")
        intervals.append(minutes)
    return intervals


def _validate_activities(activities, week) -> dict:
    """驗證本週單次活動，回傳各 id 的精確起訖時間。"""
    if activities is None:
        raise ValueError("MISSING_DATA: 活動清單必須明確提供")
    if not isinstance(activities, list):
        raise ValueError("INVALID_INPUT: 活動清單必須是 list")
    week_begin = _datetime.fromisoformat(week.isoformat() + "T00:00+08:00")
    week_end = week_begin + _timedelta(days=7)
    activity_times = {}
    for activity in activities:
        if activity is None:
            raise ValueError("MISSING_DATA: 活動資料不可為 None")
        if not isinstance(activity, dict):
            raise ValueError("INVALID_INPUT: 活動項目必須是 dict")
        for field in ("id", "name", "start", "end"):
            if field not in activity:
                raise ValueError("INVALID_INPUT: 活動缺少 id、name、start 或 end")
        for field in ("id", "name"):
            if not isinstance(activity[field], str) or not activity[field].strip():
                raise ValueError("INVALID_INPUT: 活動 id 與 name 必須是非空白 str")
        activity_id = activity["id"]
        if activity_id in activity_times:
            raise ValueError("INVALID_INPUT: 同一活動清單的 id 不得重複")

        moments = []
        for field in ("start", "end"):
            value = activity[field]
            if value is None:
                raise ValueError("MISSING_DATA: 活動起訖時間不可為 None")
            if not isinstance(value, str) or len(value) != 22 or not value.endswith("+08:00"):
                raise ValueError("INVALID_INPUT: 活動時間必須是 YYYY-MM-DDTHH:MM+08:00")
            try:
                moment = _datetime.fromisoformat(value)
            except ValueError:
                raise ValueError("INVALID_INPUT: 活動起訖時間必須有效") from None
            if moment.isoformat(timespec="minutes") != value:
                raise ValueError("INVALID_INPUT: 活動時間必須使用嚴格分鐘格式與 +08:00")
            moments.append(moment)
        start, end = moments
        if start >= end:
            raise ValueError("INVALID_INPUT: 活動 start 必須早於 end")
        if start < week_begin or end > week_end:
            raise ValueError("OUT_OF_RANGE: 活動必須完整位於指定週")
        if end.date() != start.date() and not (
            end.date() == start.date() + _timedelta(days=1)
            and end.hour == 0 and end.minute == 0
        ):
            raise ValueError("OUT_OF_RANGE: 活動須同日，僅允許結束於次日 00:00")
        activity_times[activity_id] = moments
    return activity_times


def _check_activity_consistency(first_activities, second_activities) -> None:
    """同 id 在不同清單的必要資料及已知教室須一致。"""
    first_by_id = {}
    for activity in first_activities:
        first_by_id[activity["id"]] = activity
    for activity in second_activities:
        if activity["id"] not in first_by_id:
            continue
        previous = first_by_id[activity["id"]]
        for field in ("name", "start", "end"):
            if previous[field] != activity[field]:
                raise ValueError("INVALID_INPUT: 同 id 活動的必要資料必須一致")
        if previous.get("room") is not None and activity.get("room") is not None:
            if previous["room"] != activity["room"]:
                raise ValueError("INVALID_INPUT: 同 id 活動的已知教室必須一致")


def _activity_rooms(activities) -> dict:
    """教室比較須明確提供每筆活動的 room。"""
    rooms = {}
    for activity in activities:
        room = activity.get("room")
        if room is None:
            raise ValueError("MISSING_DATA: 教室比較需要活動 room")
        if not isinstance(room, str) or not room.strip():
            raise ValueError("INVALID_INPUT: 活動 room 必須是非空白 str")
        rooms[activity["id"]] = room
    return rooms


def _periods_in_interval(start, end, period_intervals) -> list:
    """只列與實際區間有正長度交集的節次。"""
    period_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, "a", "b", "c"]
    start_minutes = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute
    if end.date() != start.date():
        end_minutes = 24 * 60
    periods = []
    for index, interval in enumerate(period_intervals):
        if start_minutes < interval[1] and interval[0] < end_minutes:
            periods.append(period_order[index])
    return periods


def _find_course_activity_overlaps(
    courses, course_ids, activities, activity_times, period_intervals,
) -> list[dict]:
    """比較課程全部時段與活動，每段連續實際交集只列一次。"""
    period_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, "a", "b", "c"]
    results = []
    for course_id in sorted(course_ids):
        for activity in activities:
            activity_start, activity_end = activity_times[activity["id"]]
            overlaps = []
            for day, period in courses[course_id]["schedule"]:
                if day != activity_start.isoweekday():
                    continue
                first_minute, last_minute = period_intervals[period_order.index(period)]
                course_start = activity_start.replace(
                    hour=first_minute // 60, minute=first_minute % 60,
                )
                course_end = activity_start.replace(
                    hour=last_minute // 60, minute=last_minute % 60,
                )
                start = max(course_start, activity_start)
                end = min(course_end, activity_end)
                if start < end:
                    overlaps.append([start, end, period])

            # 鐘點相接才合併；有實際空檔的交集保持分開。
            segments = []
            for start, end, period in sorted(overlaps, key=lambda overlap: overlap[0]):
                if segments and start == segments[-1][1]:
                    segments[-1][1] = end
                    segments[-1][2].append(period)
                else:
                    segments.append([start, end, [period]])
            for start, end, periods in segments:
                results.append({
                    "course_ids": [course_id],
                    "activity_ids": [activity["id"]],
                    "day": start.isoweekday(),
                    "periods": periods,
                    "start": start.isoformat(timespec="minutes"),
                    "end": end.isoformat(timespec="minutes"),
                })
    return results


def _find_activity_overlaps(activities, activity_times, period_intervals) -> list[dict]:
    """每對不同活動只比較一次，節次外的正長度交集也保留。"""
    ordered = sorted(activities, key=lambda activity: activity["id"])
    results = []
    for first_index in range(len(ordered)):
        first_id = ordered[first_index]["id"]
        first_start, first_end = activity_times[first_id]
        for second_index in range(first_index + 1, len(ordered)):
            second_id = ordered[second_index]["id"]
            second_start, second_end = activity_times[second_id]
            start = max(first_start, second_start)
            end = min(first_end, second_end)
            if start < end:
                results.append({
                    "course_ids": [],
                    "activity_ids": [first_id, second_id],
                    "day": start.isoweekday(),
                    "periods": _periods_in_interval(start, end, period_intervals),
                    "start": start.isoformat(timespec="minutes"),
                    "end": end.isoformat(timespec="minutes"),
                })
    return results


def _issue_sort_key(issue) -> tuple:
    """時間問題在前，以固定型別的排序鍵避開 None 與混合節次。"""
    if issue["type"] in ("student_time", "room_time"):
        period_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, "a", "b", "c"]
        period_index = 12
        if issue["periods"]:
            period_index = period_order.index(issue["periods"][0])
        return (
            0, issue["day"], period_index, issue["start"] or "",
            issue["type"], tuple(issue["course_ids"]), tuple(issue["activity_ids"]),
            issue["end"] or "", issue["room"] or "",
        )
    order = {"credit_limit": 0, "capacity": 1, "already_participating": 2}
    return (1, order[issue["type"]], issue.get("course_id", issue.get("activity_id", "")))


def check_student_state(
    courses, students, candidate_student, student_activities, room_activities, *,
    week_start, period_times=None, existing_student_id=None,
) -> dict:
    """檢查完整候選學生的個人時間、相關教室、學分與課程名額。"""
    week = _parse_week_start(week_start)
    _validate_courses(courses)
    if students is None or candidate_student is None:
        raise ValueError("MISSING_DATA: students 與 candidate_student 必須明確提供")
    if not isinstance(students, dict) or not _validate_student(candidate_student, courses):
        raise ValueError("INVALID_INPUT: 學生集合及候選學生須符合 F1 模型")
    for student_id, student in students.items():
        if student is None:
            raise ValueError("MISSING_DATA: 學生資料不可為 None")
        if not isinstance(student_id, str) or not student_id.strip():
            raise ValueError("INVALID_INPUT: 學生集合鍵必須是非空白 str")
        if not _validate_student(student, courses) or student["id"] != student_id:
            raise ValueError("INVALID_INPUT: 學生須符合 F1 模型，且 id 與集合鍵一致")

    limits = _check_student_credit_capacity(
        courses, students, candidate_student, existing_student_id=existing_student_id,
    )
    student_times = _validate_activities(student_activities, week)
    room_times = _validate_activities(room_activities, week)
    _check_activity_consistency(student_activities, room_activities)
    rooms = _activity_rooms(room_activities)
    period_intervals = None
    if period_times is not None or student_activities or room_activities:
        period_intervals = _parse_period_times(period_times)

    course_ids = candidate_student["enrolled_courses"]
    issues = _find_student_course_conflicts(courses, course_ids)
    for issue in _find_course_activity_overlaps(
        courses, course_ids, student_activities, student_times, period_intervals,
    ):
        issue["type"] = "student_time"
        issue["room"] = None
        issues.append(issue)
    for issue in _find_activity_overlaps(student_activities, student_times, period_intervals):
        issue["type"] = "student_time"
        issue["room"] = None
        issues.append(issue)

    # 教室問題至少須含一門候選課程，不回報其他配置之間的問題。
    for issue in _find_course_room_conflicts(courses):
        if any(course_id in course_ids for course_id in issue["course_ids"]):
            issues.append(issue)
    for issue in _find_course_activity_overlaps(
        courses, course_ids, room_activities, room_times, period_intervals,
    ):
        room = courses[issue["course_ids"][0]]["room"]
        if room == rooms[issue["activity_ids"][0]]:
            issue["type"] = "room_time"
            issue["room"] = room
            issues.append(issue)
    issues.extend(limits["issues"])
    issues.sort(key=_issue_sort_key)
    return {"week_start": week_start, "issues": issues, "credits": limits["credits"]}


def check_activity_participation(
    courses, student, student_activities, activity, room_activities, *,
    week_start, period_times,
) -> dict:
    """只檢查含目標活動的個人與教室時間問題，以及重複參加。"""
    week = _parse_week_start(week_start)
    _validate_courses(courses)
    if student is None:
        raise ValueError("MISSING_DATA: student 必須明確提供")
    if not _validate_student(student, courses):
        raise ValueError("INVALID_INPUT: student 須符合 F1 模型與課程參照")
    student_times = _validate_activities(student_activities, week)
    room_times = _validate_activities(room_activities, week)
    target_times = _validate_activities([activity], week)
    _check_activity_consistency(student_activities, room_activities)
    _check_activity_consistency(student_activities, [activity])
    _check_activity_consistency(room_activities, [activity])
    rooms = _activity_rooms(room_activities)
    target_room = _activity_rooms([activity])[activity["id"]]
    period_intervals = _parse_period_times(period_times)
    target_id = activity["id"]

    issues = []
    for issue in _find_course_activity_overlaps(
        courses, student["enrolled_courses"], [activity], target_times, period_intervals,
    ):
        issue["type"] = "student_time"
        issue["room"] = None
        issues.append(issue)

    # 清單中的同 id 目標以這次目標取代，只保留一份，不與自己比較。
    personal_activities = [item for item in student_activities if item["id"] != target_id]
    personal_activities.append(activity)
    personal_times = student_times.copy()
    personal_times.update(target_times)
    for issue in _find_activity_overlaps(personal_activities, personal_times, period_intervals):
        if target_id in issue["activity_ids"]:
            issue["type"] = "student_time"
            issue["room"] = None
            issues.append(issue)

    for issue in _find_course_activity_overlaps(
        courses, list(courses), [activity], target_times, period_intervals,
    ):
        if courses[issue["course_ids"][0]]["room"] == target_room:
            issue["type"] = "room_time"
            issue["room"] = target_room
            issues.append(issue)
    configured_activities = [item for item in room_activities if item["id"] != target_id]
    configured_activities.append(activity)
    configured_times = room_times.copy()
    configured_times.update(target_times)
    rooms[target_id] = target_room
    for issue in _find_activity_overlaps(configured_activities, configured_times, period_intervals):
        if target_id in issue["activity_ids"]:
            first_id, second_id = issue["activity_ids"]
            if rooms[first_id] == rooms[second_id]:
                issue["type"] = "room_time"
                issue["room"] = target_room
                issues.append(issue)
    if any(item["id"] == target_id for item in student_activities):
        issues.append({"type": "already_participating", "activity_id": target_id})
    issues.sort(key=_issue_sort_key)
    return {"week_start": week_start, "issues": issues}


def check_room_time_conflicts(courses, activities, *, week_start, period_times=None) -> dict:
    """回報同教室全部課程／活動配對的時間衝突。"""
    week = _parse_week_start(week_start)
    _validate_courses(courses)
    activity_times = _validate_activities(activities, week)
    rooms = _activity_rooms(activities)
    period_intervals = None
    if period_times is not None or activities:
        period_intervals = _parse_period_times(period_times)

    issues = _find_course_room_conflicts(courses)
    for issue in _find_course_activity_overlaps(
        courses, list(courses), activities, activity_times, period_intervals,
    ):
        room = courses[issue["course_ids"][0]]["room"]
        if room == rooms[issue["activity_ids"][0]]:
            issue["type"] = "room_time"
            issue["room"] = room
            issues.append(issue)
    for issue in _find_activity_overlaps(activities, activity_times, period_intervals):
        first_id, second_id = issue["activity_ids"]
        if rooms[first_id] == rooms[second_id]:
            issue["type"] = "room_time"
            issue["room"] = rooms[first_id]
            issues.append(issue)
    issues.sort(key=_issue_sort_key)
    return {"week_start": week_start, "issues": issues}

