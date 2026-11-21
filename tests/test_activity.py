"""F4 驗收測試。活動、課程、學生、教室及鐘點均為虛構測資。"""

from copy import deepcopy
import unittest

from modules.activity import (
    add_activity, cancel_activity, find_available_rooms, register_for_activity,
    search_activities, update_activity,
)
from modules.timetable import build_timetable


WEEK = "2026-11-16"
WEDNESDAY = "2026-11-18"
NEXT_WEEK = "2026-11-23"


def _clock():
    return [
        {"period": period, "start": f"{hour:02}:00", "end": f"{hour:02}:50"}
        for hour, period in enumerate([*range(1, 10), "a", "b", "c"], start=8)
    ]


def _activity(activity_id, start="12:00", end="13:00", *, day=WEDNESDAY, capacity=3, equipment=()):
    return {
        "id": activity_id, "name": f"測試活動 {activity_id}", "type": "講座",
        "start": f"{day}T{start}+08:00", "end": f"{day}T{end}+08:00",
        "capacity": capacity, "required_equipment": list(equipment),
    }


def _room(room_id="R1", capacity=30, equipment=()):
    return {"id": room_id, "capacity": capacity, "equipment": list(equipment)}


def _course(course_id, room, schedule):
    return {
        "id": course_id, "name": f"測試課程 {course_id}", "credits": 3,
        "required": False, "teacher": "測試教師", "capacity": 20,
        "room": room, "schedule": schedule,
    }


def _student(student_id, enrolled=()):
    return {
        "id": student_id, "name": f"測試學生 {student_id}", "department": "測試系",
        "enrolled_courses": list(enrolled), "credit_limit": 20,
    }


def _rejects(function, *args, reasons, **kwargs):
    before = deepcopy((args, kwargs))
    try:
        function(*args, **kwargs)
    except ValueError as error:
        for reason in reasons:
            assert reason in str(error), (reason, str(error))
    else:
        raise AssertionError(f"{function.__name__} 應拒絕此次操作")
    assert (args, kwargs) == before, "操作失敗時，所有輸入應保留原值"


def test_add_and_query_ten_distinct_activities():
    activities, classrooms, clock = {}, {"R1": _room()}, _clock()
    ids = [f"A{number:03}" for number in range(1, 11)]
    for hour, activity_id in enumerate(reversed(ids), start=8):
        request = _activity(activity_id, f"{hour:02}:00", f"{hour + 1:02}:00")
        created = add_activity(activities, {}, classrooms, request, period_times=clock)
        assert created == dict(request, room="R1", participants=[])
        assert "room" not in request and "participants" not in request

    assert [item["id"] for item in search_activities(activities)] == ids
    assert search_activities(activities, activity_id="A005") == [activities["A005"]]
    assert search_activities(activities, activity_id="UNKNOWN") == []
    result = search_activities(activities, activity_id="A005")[0]
    result["participants"].append("S001")
    result["required_equipment"].append("測試設備")
    assert activities["A005"]["participants"] == []
    assert activities["A005"]["required_equipment"] == []
    _rejects(
        add_activity, activities, {}, classrooms, _activity("A005"),
        period_times=clock, reasons=("活動代號 A005 已存在",),
    )


def test_room_requires_capacity_and_every_equipment_item():
    classrooms = {
        "R1": _room("R1", capacity=2, equipment=("投影機", "麥克風")),
        "R2": _room("R2", equipment=("投影機",)),
        "R3": _room("R3", equipment=("投影機", "麥克風")),
        "R4": {"id": "R4", "capacity": 30},
    }
    request = _activity("EQUIPPED", equipment=("投影機", "麥克風"))
    activities, clock = {}, _clock()
    assert find_available_rooms(activities, {}, classrooms, request, period_times=clock) == {
        "available_rooms": ["R3"],
        "rejected_rooms": {
            "R1": ["容量 2 小於預計人數 3"],
            "R2": ["缺少設備 麥克風"],
            "R4": ["缺少設備 投影機、麥克風"],
        },
    }
    assert add_activity(activities, {}, classrooms, request, period_times=clock)["room"] == "R3"


def test_no_room_reports_all_applicable_reasons():
    classrooms = {"R1": _room(capacity=2)}
    courses = {"C1": _course("C1", "R1", [[3, 4]])}
    request = _activity("NO-ROOM", "11:15", "11:45", equipment=("投影機",))
    _rejects(
        add_activity, {}, courses, classrooms, request, period_times=_clock(),
        reasons=("無可用教室", "R1", "容量 2", "缺少設備 投影機", "課程 C1"),
    )


def test_course_occupancy_and_adjacent_time():
    courses = {
        "C1": _course("C1", "R1", [[3, 3], [3, 4]]),
        "C2": _course("C2", "R1", [[3, 3]]),
    }
    activities, classrooms, clock = {}, {"R1": _room()}, _clock()
    _rejects(
        add_activity, activities, courses, classrooms, _activity("COURSE", "11:15", "11:45"),
        period_times=clock, reasons=("無可用教室", "課程 C1"),
    )
    for activity_id, start, end in (("ADJACENT", "11:50", "12:00"), ("NEXT", "12:00", "12:50")):
        request = _activity(activity_id, start, end)
        assert add_activity(activities, courses, classrooms, request, period_times=clock)["room"] == "R1"


def test_activity_occupancy_and_adjacent_time():
    activities, classrooms, clock = {}, {"R1": _room()}, _clock()
    add_activity(activities, {}, classrooms, _activity("FIRST"), period_times=clock)
    _rejects(
        add_activity, activities, {}, classrooms, _activity("SECOND", "12:59", "14:00"),
        period_times=clock, reasons=("無可用教室", "活動 FIRST"),
    )
    second = add_activity(
        activities, {}, classrooms, _activity("SECOND", "13:00", "14:00"), period_times=clock,
    )
    assert second["room"] == "R1"


def test_thirtieth_signup_succeeds_and_thirty_first_fails():
    activities, classrooms, clock = {}, {"R1": _room(capacity=30)}, _clock()
    students = {f"S{number}": _student(f"S{number}") for number in range(1, 32)}
    add_activity(activities, {}, classrooms, _activity("FULL", capacity=30), period_times=clock)
    for student_id in list(students)[:30]:
        register_for_activity(activities, "FULL", student_id, {}, classrooms, students, period_times=clock)
    assert activities["FULL"]["participants"] == list(students)[:30]
    _rejects(
        register_for_activity, activities, "FULL", "S31", {}, classrooms, students,
        period_times=clock, reasons=("額滿",),
    )


def test_signup_honors_the_lower_of_activity_and_current_room_capacity():
    students = {name: _student(name) for name in ("S1", "S2", "S3")}
    for activity_limit, room_limit in ((2, 4), (4, 2)):
        activities, classrooms, clock = {}, {"R1": _room(capacity=4)}, _clock()
        add_activity(activities, {}, classrooms, _activity("LIMIT", capacity=activity_limit), period_times=clock)
        classrooms["R1"]["capacity"] = room_limit
        for student_id in ("S1", "S2"):
            register_for_activity(activities, "LIMIT", student_id, {}, classrooms, students, period_times=clock)
        _rejects(
            register_for_activity, activities, "LIMIT", "S3", {}, classrooms, students,
            period_times=clock, reasons=("額滿", f"活動上限 {activity_limit}", f"教室容量 {room_limit}"),
        )


def test_duplicate_signup_is_rejected():
    activities, classrooms, clock = {}, {"R1": _room()}, _clock()
    students = {"S1": _student("S1")}
    add_activity(activities, {}, classrooms, _activity("SINGLE"), period_times=clock)
    register_for_activity(activities, "SINGLE", "S1", {}, classrooms, students, period_times=clock)
    _rejects(
        register_for_activity, activities, "SINGLE", "S1", {}, classrooms, students,
        period_times=clock, reasons=("已報名",),
    )


def test_signup_rejects_personal_course_conflict():
    activities, clock = {}, _clock()
    classrooms = {"R1": _room(), "R2": _room("R2")}
    courses = {"C1": _course("C1", "R2", [[3, 5]])}
    students = {"S1": _student("S1", ("C1",)), "S2": _student("S2")}
    add_activity(activities, courses, classrooms, _activity("PERSONAL"), period_times=clock)
    _rejects(
        register_for_activity, activities, "PERSONAL", "S1", courses, classrooms, students,
        period_times=clock, reasons=("學生 S1", "課程 C1"),
    )
    assert register_for_activity(
        activities, "PERSONAL", "S2", courses, classrooms, students, period_times=clock,
    )["participants"] == ["S2"]


def test_signup_rejects_personal_activity_conflict_in_another_room():
    activities, clock = {}, _clock()
    classrooms = {"R1": _room(), "R2": _room("R2")}
    students = {"S1": _student("S1")}
    first = add_activity(activities, {}, classrooms, _activity("ONCE"), period_times=clock)
    second = add_activity(activities, {}, classrooms, _activity("TWICE"), period_times=clock)
    assert (first["room"], second["room"]) == ("R1", "R2")
    register_for_activity(activities, "ONCE", "S1", {}, classrooms, students, period_times=clock)
    _rejects(
        register_for_activity, activities, "TWICE", "S1", {}, classrooms, students,
        period_times=clock, reasons=("學生 S1", "活動 ONCE"),
    )


def test_move_and_cancel_release_occupancy():
    activities, classrooms, clock = {}, {"R1": _room()}, _clock()
    students = {"S1": _student("S1")}
    add_activity(activities, {}, classrooms, _activity("MOVE"), period_times=clock)
    register_for_activity(activities, "MOVE", "S1", {}, classrooms, students, period_times=clock)
    revised = _activity("MOVE", "12:30", "13:30")
    change = {key: revised[key] for key in ("start", "end")}
    moved = update_activity(
        activities, "MOVE", change, {}, classrooms, students, period_times=clock,
    )
    assert moved["participants"] == ["S1"]
    assert search_activities(activities, activity_id="MOVE")[0]["start"] == revised["start"]

    previous_slot = _activity("PREVIOUS", "12:00", "12:30")
    add_activity(activities, {}, classrooms, previous_slot, period_times=clock)
    new_slot = _activity("REUSE", "12:30", "13:30")
    _rejects(
        add_activity, activities, {}, classrooms, new_slot, period_times=clock,
        reasons=("無可用教室", "活動 MOVE"),
    )
    assert cancel_activity(activities, "MOVE") == moved
    assert search_activities(activities, student_id="S1") == []
    assert add_activity(activities, {}, classrooms, new_slot, period_times=clock)["room"] == "R1"


def test_failed_move_preserves_the_old_booking_and_signup():
    activities, classrooms, clock = {}, {"R1": _room()}, _clock()
    students = {"S1": _student("S1")}
    courses = {"C1": _course("C1", "R1", [[3, 4]])}
    add_activity(activities, courses, classrooms, _activity("KEEP"), period_times=clock)
    register_for_activity(activities, "KEEP", "S1", courses, classrooms, students, period_times=clock)
    blocked = _activity("KEEP", "11:10", "11:30")
    changes = {key: blocked[key] for key in ("start", "end")}
    _rejects(
        update_activity, activities, "KEEP", changes, courses, classrooms, students,
        period_times=clock, reasons=("無可用教室", "課程 C1"),
    )
    _rejects(
        add_activity, activities, courses, classrooms, _activity("STILL-BOOKED"),
        period_times=clock, reasons=("無可用教室", "活動 KEEP"),
    )


def test_move_checks_previous_signups_against_the_new_time():
    activities, clock = {}, _clock()
    classrooms = {"R1": _room(), "R2": _room("R2")}
    courses = {"C1": _course("C1", "R2", [[3, 4]])}
    students = {"S1": _student("S1"), "S2": _student("S2", ("C1",))}
    add_activity(activities, courses, classrooms, _activity("KEEP"), period_times=clock)
    for student_id in students:
        register_for_activity(activities, "KEEP", student_id, courses, classrooms, students, period_times=clock)
    blocked = _activity("KEEP", "11:10", "11:30")
    changes = {key: blocked[key] for key in ("start", "end")}
    _rejects(
        update_activity, activities, "KEEP", changes, courses, classrooms, students,
        period_times=clock, reasons=("學生 S2", "課程 C1"),
    )
    _rejects(
        update_activity, activities, "KEEP", {"capacity": 1}, courses, classrooms, students,
        period_times=clock, reasons=("不可低於目前報名的 2 人",),
    )


def test_student_week_query_can_feed_f3():
    activities, classrooms, clock = {}, {"R1": _room()}, _clock()
    students = {"S1": _student("S1")}
    for activity_id, day in (("THIS-WEEK", WEEK), ("NEXT-WEEK", NEXT_WEEK), ("NOT-JOINED", WEDNESDAY)):
        add_activity(activities, {}, classrooms, _activity(activity_id, day=day), period_times=clock)
    for activity_id in ("THIS-WEEK", "NEXT-WEEK"):
        register_for_activity(activities, activity_id, "S1", {}, classrooms, students, period_times=clock)
    results = search_activities(activities, student_id="S1", week_start=WEEK)
    timetable = build_timetable({}, students["S1"], results, week_start=WEEK, period_times=clock)
    assert [item["id"] for item in timetable["activities"]] == ["THIS-WEEK"]
    assert [item["id"] for item in timetable["grid"][0][4]] == ["THIS-WEEK"]


def test_invalid_activity_fields_are_rejected():
    activity = _activity("INVALID")
    invalid_fields = (
        ("id", "", "活動代號"), ("name", " ", "活動名稱"), ("type", None, "活動類型"),
        ("start", "2026-11-31T12:00+08:00", "日期與時間"),
        ("start", "2026-11-18T24:00+08:00", "日期與時間"),
        ("end", activity["start"], "開始時間必須早於結束時間"),
        ("end", "2026-11-19T01:00+08:00", "同一天"),
        ("capacity", 0, "正整數"), ("capacity", True, "正整數"),
        ("required_equipment", "投影機", "設備名稱清單"),
        ("required_equipment", [" "], "設備名稱"),
        ("required_equipment", ["投影機", "投影機"], "重複設備"),
    )
    for field, value, reason in invalid_fields:
        invalid = dict(activity, **{field: value})
        _rejects(
            add_activity, {}, {}, {"R1": _room()}, invalid,
            period_times=_clock(), reasons=(reason,),
        )


def test_missing_or_incomplete_clock_rejects_booking():
    for clock, reason in ((None, "缺少鐘點表"), (_clock()[:-1], "MISSING_DATA")):
        _rejects(
            add_activity, {}, {}, {"R1": _room()}, _activity("CLOCK"),
            period_times=clock, reasons=(reason,),
        )


def load_tests(loader, tests, pattern):
    functions = [
        test_add_and_query_ten_distinct_activities,
        test_room_requires_capacity_and_every_equipment_item,
        test_no_room_reports_all_applicable_reasons,
        test_course_occupancy_and_adjacent_time,
        test_activity_occupancy_and_adjacent_time,
        test_thirtieth_signup_succeeds_and_thirty_first_fails,
        test_signup_honors_the_lower_of_activity_and_current_room_capacity,
        test_duplicate_signup_is_rejected,
        test_signup_rejects_personal_course_conflict,
        test_signup_rejects_personal_activity_conflict_in_another_room,
        test_move_and_cancel_release_occupancy,
        test_failed_move_preserves_the_old_booking_and_signup,
        test_move_checks_previous_signups_against_the_new_time,
        test_student_week_query_can_feed_f3,
        test_invalid_activity_fields_are_rejected,
        test_missing_or_incomplete_clock_rejects_booking,
    ]
    return unittest.TestSuite(unittest.FunctionTestCase(function) for function in functions)


if __name__ == "__main__":
    unittest.main()
