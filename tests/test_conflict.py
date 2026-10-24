"""F2 契約測試；全部鐘點、課程、學生與活動均為合成測資。

使用 unittest.FunctionTestCase，保留一般函式寫法，不新增測試類別。
"""
from copy import deepcopy
from datetime import date, datetime
import unittest

from modules.conflict import (
    check_student_state, check_activity_participation, check_room_time_conflicts,
)

WEEK = "2026-10-19"


def _course(course_id="C1", schedule=None, credits=3, capacity=5, room="R1"):
    return {"id": course_id, "name": "Course " + course_id, "credits": credits,
            "required": False, "teacher": "Teacher", "capacity": capacity,
            "room": room, "schedule": [[1, 1]] if schedule is None else schedule}


def _student(student_id="S1", courses=None, limit=18):
    return {"id": student_id, "name": "Student " + student_id, "department": "D",
            "enrolled_courses": [] if courses is None else list(courses),
            "credit_limit": limit}


def _clock():
    # 合成鐘點：08:00 起每小時一節、每節 45 分鐘，非正式學校鐘點。
    return [{"period": period, "start": f"{8+i:02d}:00", "end": f"{8+i:02d}:45"}
            for i, period in enumerate([1, 2, 3, 4, 5, 6, 7, 8, 9, "a", "b", "c"])]


def _activity(activity_id="A1", start="08:10", end="08:30", room="R1", day=WEEK):
    result = {"id": activity_id, "name": "Activity " + activity_id,
              "start": day + "T" + start + "+08:00", "end": day + "T" + end + "+08:00"}
    if room is not None:
        result["room"] = room
    return result


def _time(kind, courses=None, activities=None, day=1, periods=None,
          start=None, end=None, room=None):
    return {"type": kind, "course_ids": [] if courses is None else courses,
            "activity_ids": [] if activities is None else activities, "day": day,
            "periods": [] if periods is None else periods, "start": start, "end": end,
            "room": room}


def _error(prefix, function, *args, **kwargs):
    before = deepcopy((args, kwargs))
    try:
        function(*args, **kwargs)
    except ValueError as error:
        assert str(error).startswith(prefix + ": "), str(error)
    else:
        raise AssertionError("Expected " + prefix)
    assert (args, kwargs) == before, "Error path modified input"


def test_normal_empty_candidate():
    result = check_student_state({}, {}, _student(), [], [], week_start=WEEK)
    assert result == {"week_start": WEEK, "issues": [],
                      "credits": {"before": 0, "after": 0, "limit": 18}}


def test_normal_new_student_with_courses():
    courses = {"C1": _course(), "C2": _course("C2", [[2, 1]], room="R2")}
    result = check_student_state(courses, {}, _student(courses=["C1", "C2"]), [], [],
                                 week_start=WEEK)
    assert result == {"week_start": WEEK, "issues": [],
                      "credits": {"before": 0, "after": 6, "limit": 18}}


def test_normal_update_replaces_original_credits():
    courses = {"C1": _course(), "C2": _course("C2", [[2, 1]], credits=4)}
    students = {"S1": _student(courses=["C1"])}
    result = check_student_state(courses, students, _student(courses=["C2"], limit=4),
                                 [], [], week_start=WEEK, existing_student_id="S1")
    assert result["credits"] == {"before": 3, "after": 4, "limit": 4}
    assert result["issues"] == []


def test_normal_all_candidate_pairs_and_slots():
    courses = {"C1": _course(schedule=[[1, 3], [1, 1]], room="R1"),
               "C2": _course("C2", [[1, 1], [1, 3]], room="R2"),
               "C3": _course("C3", [[1, 1]], room="R3")}
    result = check_student_state(courses, {}, _student(courses=["C3", "C2", "C1"]),
                                 [], [], week_start=WEEK)
    assert result["issues"] == [
        _time("student_time", ["C1", "C2"], periods=[1]),
        _time("student_time", ["C1", "C3"], periods=[1]),
        _time("student_time", ["C2", "C3"], periods=[1]),
        _time("student_time", ["C1", "C2"], periods=[3]),
    ]


def test_normal_all_same_room_course_pairs():
    courses = {key: _course(key, [[1, 2]]) for key in ["C3", "C1", "C2"]}
    courses["C4"] = _course("C4", [[1, 2]], room="R2")
    result = check_room_time_conflicts(courses, [], week_start=WEEK)
    assert result["issues"] == [
        _time("room_time", ["C1", "C2"], periods=[2], room="R1"),
        _time("room_time", ["C1", "C3"], periods=[2], room="R1"),
        _time("room_time", ["C2", "C3"], periods=[2], room="R1"),
    ]


def test_normal_student_room_scope_excludes_unrelated_pairs():
    courses = {"A": _course("A"), "B": _course("B"),
               "C": _course("C", [[1, 3]], room="R2"),
               "D": _course("D", [[1, 3]], room="R2")}
    result = check_student_state(courses, {}, _student(courses=["A"]), [], [],
                                 week_start=WEEK)
    assert result["issues"] == [_time("room_time", ["A", "B"], periods=[1], room="R1")]


def test_normal_participation_only_target_issues():
    courses = {"C1": _course(room="R3")}
    target = _activity("T", "08:10", "08:20")
    others = [_activity("A", "09:10", "09:30", "R2"),
              _activity("B", "09:20", "09:40", "R2")]
    result = check_activity_participation(courses, _student(courses=["C1"]), others,
                                         target, others, week_start=WEEK, period_times=_clock())
    assert result["issues"] == [
        _time("student_time", ["C1"], ["T"], periods=[1],
              start=WEEK+"T08:10+08:00", end=WEEK+"T08:20+08:00"),
    ]


def test_normal_personal_and_room_reasons_preserved():
    activity = _activity()
    result = check_student_state({"C1": _course()}, {}, _student(courses=["C1"]),
                                 [activity], [activity], week_start=WEEK, period_times=_clock())
    assert result["issues"] == [
        _time("room_time", ["C1"], ["A1"], periods=[1],
              start=WEEK+"T08:10+08:00", end=WEEK+"T08:30+08:00", room="R1"),
        _time("student_time", ["C1"], ["A1"], periods=[1],
              start=WEEK+"T08:10+08:00", end=WEEK+"T08:30+08:00"),
    ]


def test_normal_room_course_and_activity_pairs():
    courses = {"C2": _course("C2"), "C1": _course()}
    activities = [_activity("A2", "08:20", "08:35"), _activity("A1", "08:10", "08:30")]
    result = check_room_time_conflicts(courses, activities, week_start=WEEK, period_times=_clock())
    assert result["issues"] == [
        _time("room_time", ["C1", "C2"], periods=[1], room="R1"),
        _time("room_time", ["C1"], ["A1"], periods=[1],
              start=WEEK+"T08:10+08:00", end=WEEK+"T08:30+08:00", room="R1"),
        _time("room_time", ["C2"], ["A1"], periods=[1],
              start=WEEK+"T08:10+08:00", end=WEEK+"T08:30+08:00", room="R1"),
        _time("room_time", activities=["A1", "A2"], periods=[1],
              start=WEEK+"T08:20+08:00", end=WEEK+"T08:30+08:00", room="R1"),
        _time("room_time", ["C1"], ["A2"], periods=[1],
              start=WEEK+"T08:20+08:00", end=WEEK+"T08:35+08:00", room="R1"),
        _time("room_time", ["C2"], ["A2"], periods=[1],
              start=WEEK+"T08:20+08:00", end=WEEK+"T08:35+08:00", room="R1"),
    ]


def test_normal_already_participating_still_reports_conflicts():
    target = _activity("A", "08:10", "08:40")
    other = _activity("B", "08:20", "08:30")
    result = check_activity_participation({"C1": _course()}, _student(courses=["C1"]),
                                         [target, other], target, [other, target],
                                         week_start=WEEK, period_times=_clock())
    assert result["issues"] == [
        _time("room_time", ["C1"], ["A"], periods=[1],
              start=WEEK+"T08:10+08:00", end=WEEK+"T08:40+08:00", room="R1"),
        _time("student_time", ["C1"], ["A"], periods=[1],
              start=WEEK+"T08:10+08:00", end=WEEK+"T08:40+08:00"),
        _time("room_time", activities=["A", "B"], periods=[1],
              start=WEEK+"T08:20+08:00", end=WEEK+"T08:30+08:00", room="R1"),
        _time("student_time", activities=["A", "B"], periods=[1],
              start=WEEK+"T08:20+08:00", end=WEEK+"T08:30+08:00"),
        {"type": "already_participating", "activity_id": "A"},
    ]


def test_normal_course_and_activity_can_share_id():
    target = _activity("C1")
    result = check_activity_participation({"C1": _course()}, _student(courses=["C1"]),
                                         [], target, [], week_start=WEEK, period_times=_clock())
    assert len(result["issues"]) == 2
    assert [issue["type"] for issue in result["issues"]] == ["room_time", "student_time"]
    for issue in result["issues"]:
        assert issue["course_ids"] == ["C1"] and issue["activity_ids"] == ["C1"]


def test_normal_personal_activity_does_not_need_room():
    result = check_student_state({"C1": _course()}, {}, _student(courses=["C1"]),
                                 [_activity(room=None)], [], week_start=WEEK, period_times=_clock())
    assert result["issues"] == [
        _time("student_time", ["C1"], ["A1"], periods=[1],
              start=WEEK+"T08:10+08:00", end=WEEK+"T08:30+08:00"),
    ]


def test_normal_success_inputs_and_issue_results_independent():
    courses = {"C1": _course(), "C2": _course("C2")}
    candidate = _student(courses=["C1", "C2"])
    before = deepcopy((courses, candidate))
    result = check_student_state(courses, {}, candidate, [], [], week_start=WEEK)
    assert (courses, candidate) == before
    assert len(result["issues"]) == 2
    result["issues"][0]["course_ids"].append("changed")
    result["issues"][0]["periods"].append("c")
    result["credits"]["after"] = 999
    assert result["issues"][1]["course_ids"] == ["C1", "C2"]
    assert result["issues"][1]["periods"] == [1]
    assert (courses, candidate) == before


def test_normal_participation_inputs_unchanged():
    target = _activity()
    inputs = ({}, _student(), [], target, [deepcopy(target)])
    before = deepcopy(inputs)
    result = check_activity_participation(*inputs, week_start=WEEK, period_times=_clock())
    assert result == {"week_start": WEEK, "issues": []}
    assert inputs == before
    result["issues"].append({"type": "changed"})
    assert inputs == before


def test_boundary_new_capacity_exactly_full():
    courses = {"C1": _course(capacity=2)}
    result = check_student_state(courses, {"S2": _student("S2", ["C1"])},
                                 _student(courses=["C1"]), [], [], week_start=WEEK)
    assert result["issues"] == []
    assert result["credits"]["after"] == 3


def test_boundary_retained_course_not_counted_twice():
    courses = {"C1": _course(capacity=1)}
    original = _student(courses=["C1"])
    result = check_student_state(courses, {"S1": original}, deepcopy(original), [], [],
                                 week_start=WEEK, existing_student_id="S1")
    assert result["issues"] == []
    assert result["credits"] == {"before": 3, "after": 3, "limit": 18}


def test_boundary_added_removed_and_unrelated_capacity():
    courses = {"C1": _course(capacity=1), "C2": _course("C2", [[2, 1]], credits=4, capacity=2),
               "C3": _course("C3", [[3, 1]], capacity=1)}
    students = {"S1": _student(courses=["C1"]),
                "S2": _student("S2", ["C1", "C2", "C3"]),
                "S3": _student("S3", ["C1", "C3"])}
    result = check_student_state(courses, students, _student(courses=["C2"]), [], [],
                                 week_start=WEEK, existing_student_id="S1")
    assert result["issues"] == []
    assert result["credits"] == {"before": 3, "after": 4, "limit": 18}


def test_boundary_credits_equal_limit():
    courses = {"C1": _course(), "C2": _course("C2", [[2, 1]])}
    result = check_student_state(courses, {}, _student(courses=["C1", "C2"], limit=6),
                                 [], [], week_start=WEEK)
    assert result["issues"] == []
    assert result["credits"] == {"before": 0, "after": 6, "limit": 6}


def test_boundary_only_limit_changed():
    courses = {"C1": _course(credits=6)}
    result = check_student_state(courses, {"S1": _student(courses=["C1"])},
                                 _student(courses=["C1"], limit=5), [], [],
                                 week_start=WEEK, existing_student_id="S1")
    assert result["issues"] == [{"type": "credit_limit"}]
    assert result["credits"] == {"before": 6, "after": 6, "limit": 5}


def test_boundary_update_to_empty_selection():
    courses = {"C1": _course(credits=6, capacity=1)}
    students = {"S1": _student(courses=["C1"]), "S2": _student("S2", ["C1"])}
    result = check_student_state(courses, students, _student(), [], [], week_start=WEEK,
                                 existing_student_id="S1")
    assert result["issues"] == []
    assert result["credits"] == {"before": 6, "after": 0, "limit": 18}


def test_boundary_retained_course_already_over_capacity():
    courses = {"C1": _course(capacity=1)}
    students = {"S1": _student(courses=["C1"]), "S2": _student("S2", ["C1"])}
    result = check_student_state(courses, students, _student(courses=["C1"]), [], [],
                                 week_start=WEEK, existing_student_id="S1")
    assert result["issues"] == [
        {"type": "capacity", "course_id": "C1", "enrolled": 2, "capacity": 1}]


def test_boundary_all_credit_and_capacity_issues_ordered():
    courses = {"C2": _course("C2", [[1, 1]], capacity=1), "C1": _course(capacity=1)}
    students = {"S2": _student("S2", ["C1", "C2"])}
    result = check_student_state(courses, students, _student(courses=["C2", "C1"], limit=5),
                                 [], [], week_start=WEEK)
    assert result["issues"] == [
        _time("room_time", ["C1", "C2"], periods=[1], room="R1"),
        _time("student_time", ["C1", "C2"], periods=[1]),
        {"type": "credit_limit"},
        {"type": "capacity", "course_id": "C1", "enrolled": 2, "capacity": 1},
        {"type": "capacity", "course_id": "C2", "enrolled": 2, "capacity": 1},
    ]


def test_boundary_half_open_course_activity_endpoints():
    courses = {"C1": _course(schedule=[[1, 1], [1, 2]])}
    result = check_room_time_conflicts(courses, [_activity(start="08:45", end="09:00")],
                                       week_start=WEEK, period_times=_clock())
    assert result["issues"] == []
    target = _activity("A", "08:00", "08:10")
    other = _activity("B", "08:10", "08:20")
    result = check_activity_participation({}, _student(), [other], target, [other],
                                         week_start=WEEK, period_times=_clock())
    assert result["issues"] == []


def test_boundary_same_grid_cell_not_actual_activity_overlap():
    target = _activity("A", "08:00", "08:10")
    other = _activity("B", "08:20", "08:30")
    result = check_activity_participation({}, _student(), [other], target, [other],
                                         week_start=WEEK, period_times=_clock())
    assert result["issues"] == []


def test_boundary_contiguous_course_intersections_merge():
    clock = _clock()
    clock[0]["end"] = "09:00"
    result = check_room_time_conflicts({"C1": _course(schedule=[[1, 2], [1, 1]])},
                                       [_activity(start="08:30", end="09:30")],
                                       week_start=WEEK, period_times=clock)
    assert result["issues"] == [
        _time("room_time", ["C1"], ["A1"], periods=[1, 2],
              start=WEEK+"T08:30+08:00", end=WEEK+"T09:30+08:00", room="R1")]


def test_boundary_separate_course_intersections_stay_separate():
    result = check_room_time_conflicts({"C1": _course(schedule=[[1, 1], [1, 2]])},
                                       [_activity(start="08:30", end="09:30")],
                                       week_start=WEEK, period_times=_clock())
    assert result["issues"] == [
        _time("room_time", ["C1"], ["A1"], periods=[1],
              start=WEEK+"T08:30+08:00", end=WEEK+"T08:45+08:00", room="R1"),
        _time("room_time", ["C1"], ["A1"], periods=[2],
              start=WEEK+"T09:00+08:00", end=WEEK+"T09:30+08:00", room="R1"),
    ]


def test_boundary_off_period_activity_overlap():
    result = check_room_time_conflicts({}, [_activity("A", "22:00", "22:30"),
                                             _activity("B", "22:10", "22:20")],
                                       week_start=WEEK, period_times=_clock())
    assert result["issues"] == [
        _time("room_time", activities=["A", "B"],
              start=WEEK+"T22:10+08:00", end=WEEK+"T22:20+08:00", room="R1")]


def test_boundary_sunday_activity_can_end_next_monday_midnight():
    first = _activity("A", "23:00", "23:59", day="2026-10-25")
    first["end"] = "2026-10-26T00:00+08:00"
    second = _activity("B", "23:30", "23:45", day="2026-10-25")
    result = check_room_time_conflicts({}, [first, second], week_start=WEEK, period_times=_clock())
    assert result["issues"] == [
        _time("room_time", activities=["A", "B"], day=7,
              start="2026-10-25T23:30+08:00", end="2026-10-25T23:45+08:00", room="R1")]


def test_boundary_mixed_period_and_day_order():
    slots = [[7, "c"], [1, "b"], [1, 9], [1, "a"], [1, 1]]
    courses = {"B": _course("B", deepcopy(slots)), "A": _course("A", deepcopy(slots))}
    result = check_room_time_conflicts(courses, [], week_start=WEEK)
    assert result["issues"] == [
        _time("room_time", ["A", "B"], day=day, periods=[period], room="R1")
        for day, period in [[1, 1], [1, 9], [1, "a"], [1, "b"], [7, "c"]]]


def test_error_student_modes():
    courses = {"C1": _course()}
    original = _student(courses=["C1"])
    _error("INVALID_INPUT", check_student_state, courses, {"S1": original}, original,
           [], [], week_start=WEEK)
    for existing in ["missing", False, " "]:
        _error("INVALID_INPUT", check_student_state, courses, {}, original, [], [],
               week_start=WEEK, existing_student_id=existing)
    _error("INVALID_INPUT", check_student_state, courses, {"S2": _student("S2")},
           original, [], [], week_start=WEEK, existing_student_id="S2")


def test_error_existing_student_missing():
    courses = {}
    students = {}
    candidate = _student("missing", courses=[])
    student_activities = []
    room_activities = []
    _error("INVALID_INPUT", check_student_state, courses, students, candidate,
           student_activities, room_activities, week_start=WEEK,
           existing_student_id="missing")


def test_error_missing_required_student_data():
    valid = [{}, {}, _student(), [], []]
    for index in range(5):
        args = deepcopy(valid)
        args[index] = None
        _error("MISSING_DATA", check_student_state, *args, week_start=WEEK)
    _error("MISSING_DATA", check_student_state, {}, {"S1": None}, _student("S2"),
           [], [], week_start=WEEK)


def test_error_f1_student_models_and_references():
    for field, value in [("id", " "), ("credit_limit", True), ("credit_limit", 0),
                         ("enrolled_courses", ["missing"]), ("enrolled_courses", ["C1", "C1"]),
                         ("enrolled_courses", None), ("name", ""), ("department", 1)]:
        candidate = _student()
        candidate[field] = value
        _error("INVALID_INPUT", check_student_state, {"C1": _course()}, {}, candidate,
               [], [], week_start=WEEK)
    extra = _student()
    extra["extra"] = 1
    _error("INVALID_INPUT", check_student_state, {}, {}, extra, [], [], week_start=WEEK)
    _error("INVALID_INPUT", check_student_state, {}, {"wrong": _student()}, _student("S2"),
           [], [], week_start=WEEK)
    _error("INVALID_INPUT", check_student_state, {}, [], _student(), [], [], week_start=WEEK)


def test_error_course_models_and_slot_types():
    variants = [("id", "different"), ("credits", True), ("capacity", 1.5),
                ("required", 1), ("room", ""), ("schedule", []),
                ("schedule", [[True, 1]]), ("schedule", [[1, True]]),
                ("schedule", [[1, "A"]]), ("schedule", [[1, 1], [1, 1]])]
    for field, value in variants:
        course = _course()
        course[field] = value
        _error("INVALID_INPUT", check_room_time_conflicts, {"C1": course}, [], week_start=WEEK)
    _error("INVALID_INPUT", check_room_time_conflicts, [], [], week_start=WEEK)
    _error("INVALID_INPUT", check_room_time_conflicts, {" ": _course(" ")}, [], week_start=WEEK)


def test_error_missing_course_room_and_schedule():
    for courses in [None, {"C1": None}, {"C1": {**_course(), "room": None}},
                    {"C1": {**_course(), "schedule": None}}]:
        _error("MISSING_DATA", check_room_time_conflicts, courses, [], week_start=WEEK)


def test_error_week_start_strict_monday_and_range():
    values = ["2026-10-20", "20261019", "2026-10-19T00:00", "2026-02-30",
              "", 20261019, date(2026, 10, 19), "9999-12-27"]
    for value in values:
        _error("INVALID_INPUT", check_room_time_conflicts, {}, [], week_start=value)
    _error("MISSING_DATA", check_room_time_conflicts, {}, [], week_start=None)


def test_error_activity_time_format_and_duration():
    values = ["2026-10-19T08:10:00+08:00", "2026-10-19T00:10Z",
              "2026-10-19T08:10+09:00", "2026-10-19 08:10+08:00",
              "2026-13-19T08:10+08:00", "2026-10-19T08:10",
              datetime(2026, 10, 19, 8, 10), "2026-10-19T08:10:00", 1]
    for value in values:
        activity = _activity()
        activity["start"] = value
        _error("INVALID_INPUT", check_room_time_conflicts, {}, [activity],
               week_start=WEEK, period_times=_clock())
    for start, end in [("08:30", "08:30"), ("08:40", "08:30")]:
        _error("INVALID_INPUT", check_room_time_conflicts, {}, [_activity(start=start, end=end)],
               week_start=WEEK, period_times=_clock())


def test_error_outside_week_and_unsupported_cross_day():
    variants = [("2026-10-18T08:00+08:00", "2026-10-18T09:00+08:00"),
                ("2026-10-18T23:30+08:00", "2026-10-19T00:30+08:00"),
                ("2026-10-25T23:30+08:00", "2026-10-26T00:01+08:00"),
                ("2026-10-19T23:30+08:00", "2026-10-20T00:01+08:00"),
                ("2026-10-26T08:00+08:00", "2026-10-26T09:00+08:00")]
    for start, end in variants:
        target = _activity()
        target.update(start=start, end=end)
        _error("OUT_OF_RANGE", check_activity_participation, {}, _student(), [], target, [],
               week_start=WEEK, period_times=_clock())


def test_error_incomplete_clock_is_missing_data():
    clocks = [None, [], _clock()[:-1]]
    for field in ["period", "start", "end"]:
        clock = _clock()
        del clock[0][field]
        clocks.append(clock)
    clock = _clock()
    clock[0] = None
    clocks.append(clock)
    for clock in clocks:
        _error("MISSING_DATA", check_room_time_conflicts, {}, [_activity()],
               week_start=WEEK, period_times=clock)


def test_error_invalid_clock_types_order_and_intervals():
    clocks = [{}, _clock()+[_clock()[0]]]
    for field, value in [("period", True), ("period", 2), ("start", "8:00"),
                         ("start", "24:00"), ("start", 800), ("end", "08:00")]:
        clock = _clock()
        clock[0][field] = value
        clocks.append(clock)
    clock = _clock()
    clock[1]["start"] = "08:30"
    clocks.append(clock)
    clock = _clock()
    clock[0] = []
    clocks.append(clock)
    for clock in clocks:
        _error("INVALID_INPUT", check_room_time_conflicts, {}, [_activity()],
               week_start=WEEK, period_times=clock)


def test_error_activity_list_and_required_fields():
    _error("MISSING_DATA", check_room_time_conflicts, {}, None, week_start=WEEK)
    _error("INVALID_INPUT", check_room_time_conflicts, {}, {}, week_start=WEEK)
    _error("MISSING_DATA", check_room_time_conflicts, {}, [None], week_start=WEEK)
    _error("INVALID_INPUT", check_room_time_conflicts, {}, [[]], week_start=WEEK)
    for field, value in [("id", " "), ("name", 1), ("start", None), ("end", None)]:
        activity = _activity()
        activity[field] = value
        prefix = "MISSING_DATA" if value is None else "INVALID_INPUT"
        _error(prefix, check_room_time_conflicts, {}, [activity], week_start=WEEK,
               period_times=_clock())
    activity = _activity()
    del activity["start"]
    _error("INVALID_INPUT", check_room_time_conflicts, {}, [activity],
           week_start=WEEK, period_times=_clock())


def test_error_duplicate_and_inconsistent_activity_ids():
    target = _activity()
    _error("INVALID_INPUT", check_room_time_conflicts, {}, [target, deepcopy(target)],
           week_start=WEEK, period_times=_clock())
    for field, value in [("name", "different"), ("start", WEEK+"T08:11+08:00"),
                         ("end", WEEK+"T08:31+08:00"), ("room", "R2")]:
        other = deepcopy(target)
        other[field] = value
        _error("INVALID_INPUT", check_student_state, {}, {}, _student(), [target], [other],
               week_start=WEEK, period_times=_clock())
        _error("INVALID_INPUT", check_activity_participation, {}, _student(), [other], target, [],
               week_start=WEEK, period_times=_clock())


def test_error_unknown_room_never_skipped():
    _error("MISSING_DATA", check_room_time_conflicts, {}, [_activity(room=None)],
           week_start=WEEK, period_times=_clock())
    _error("MISSING_DATA", check_activity_participation, {}, _student(), [], _activity(room=None),
           [], week_start=WEEK, period_times=_clock())
    for room in [" ", 1]:
        _error("INVALID_INPUT", check_room_time_conflicts, {}, [_activity(room=room)],
               week_start=WEEK, period_times=_clock())
    _error("MISSING_DATA", check_activity_participation, {}, _student(), [_activity(room=None)],
           _activity(room=None), [], week_start=WEEK, period_times=_clock())


def test_normal_student_all_existing_activity_pairs():
    activities = [_activity("C", "08:25", "08:35", "R3"),
                  _activity("A", "08:10", "08:40", "R1"),
                  _activity("B", "08:20", "08:30", "R2")]
    before = deepcopy(activities)
    result = check_student_state({}, {}, _student(), activities, [],
                                 week_start=WEEK, period_times=_clock())
    assert result["issues"] == [
        _time("student_time", activities=["A", "B"], periods=[1],
              start=WEEK+"T08:20+08:00", end=WEEK+"T08:30+08:00"),
        _time("student_time", activities=["A", "C"], periods=[1],
              start=WEEK+"T08:25+08:00", end=WEEK+"T08:35+08:00"),
        _time("student_time", activities=["B", "C"], periods=[1],
              start=WEEK+"T08:25+08:00", end=WEEK+"T08:30+08:00"),
    ]
    assert activities == before


def test_normal_activity_room_filters_in_all_public_scopes():
    courses = {"C1": _course()}
    other = _activity("B", room="R2")
    target = _activity("A", room="R1")
    inputs = deepcopy((courses, other, target))
    assert check_room_time_conflicts(courses, [other], week_start=WEEK,
                                     period_times=_clock())["issues"] == []
    assert check_room_time_conflicts({}, [target, other], week_start=WEEK,
                                     period_times=_clock())["issues"] == []
    assert check_student_state(courses, {}, _student(courses=["C1"]), [], [other],
                               week_start=WEEK, period_times=_clock())["issues"] == []
    result = check_activity_participation({}, _student(), [other], target, [other],
                                         week_start=WEEK, period_times=_clock())
    assert result["issues"] == [
        _time("student_time", activities=["A", "B"], periods=[1],
              start=WEEK+"T08:10+08:00", end=WEEK+"T08:30+08:00")]
    assert (courses, other, target) == inputs


def test_error_participation_student_and_collection_key():
    _error("MISSING_DATA", check_activity_participation, {}, None, [], _activity(), [],
           week_start=WEEK, period_times=_clock())
    _error("INVALID_INPUT", check_activity_participation, {}, {}, [], _activity(), [],
           week_start=WEEK, period_times=_clock())
    _error("INVALID_INPUT", check_student_state, {}, {" ": _student()}, _student("S2"),
           [], [], week_start=WEEK)



def load_tests(loader, tests, pattern):
    # 標準 unittest discovery 入口；每個明列函式是一個可獨立重跑的測試。
    functions = [
        test_normal_student_all_existing_activity_pairs,
        test_normal_activity_room_filters_in_all_public_scopes,
        test_error_participation_student_and_collection_key,
        test_normal_empty_candidate, test_normal_new_student_with_courses,
        test_normal_update_replaces_original_credits, test_normal_all_candidate_pairs_and_slots,
        test_normal_all_same_room_course_pairs, test_normal_student_room_scope_excludes_unrelated_pairs,
        test_normal_participation_only_target_issues, test_normal_personal_and_room_reasons_preserved,
        test_normal_room_course_and_activity_pairs, test_normal_already_participating_still_reports_conflicts,
        test_normal_course_and_activity_can_share_id, test_normal_personal_activity_does_not_need_room,
        test_normal_success_inputs_and_issue_results_independent, test_normal_participation_inputs_unchanged,
        test_boundary_new_capacity_exactly_full, test_boundary_retained_course_not_counted_twice,
        test_boundary_added_removed_and_unrelated_capacity, test_boundary_credits_equal_limit,
        test_boundary_only_limit_changed, test_boundary_update_to_empty_selection,
        test_boundary_retained_course_already_over_capacity, test_boundary_all_credit_and_capacity_issues_ordered,
        test_boundary_half_open_course_activity_endpoints, test_boundary_same_grid_cell_not_actual_activity_overlap,
        test_boundary_contiguous_course_intersections_merge, test_boundary_separate_course_intersections_stay_separate,
        test_boundary_off_period_activity_overlap, test_boundary_sunday_activity_can_end_next_monday_midnight,
        test_boundary_mixed_period_and_day_order, test_error_student_modes,
        test_error_existing_student_missing,
        test_error_missing_required_student_data, test_error_f1_student_models_and_references,
        test_error_course_models_and_slot_types, test_error_missing_course_room_and_schedule,
        test_error_week_start_strict_monday_and_range, test_error_activity_time_format_and_duration,
        test_error_outside_week_and_unsupported_cross_day, test_error_incomplete_clock_is_missing_data,
        test_error_invalid_clock_types_order_and_intervals, test_error_activity_list_and_required_fields,
        test_error_duplicate_and_inconsistent_activity_ids, test_error_unknown_room_never_skipped,
    ]
    return unittest.TestSuite(unittest.FunctionTestCase(function) for function in functions)


if __name__ == "__main__":
    unittest.main()

