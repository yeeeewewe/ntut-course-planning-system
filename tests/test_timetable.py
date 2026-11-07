"""F3 契約與 F1→F2→F3 核心串接測試；全部資料均為合成資料。"""
from copy import deepcopy
import unittest

from modules.course import validate_course
from modules.student import validate_student
from modules.conflict import check_student_state
from modules.timetable import (
    build_timetable, query_timetable, find_free_periods, summarize_timetable,
)

WEEK = "2026-10-19"
PERIODS = [1, 2, 3, 4, 5, 6, 7, 8, 9, "a", "b", "c"]


def _course(course_id="C1", schedule=None, credits=3):
    return {"id": course_id, "name": "Course " + course_id, "credits": credits,
            "required": False, "teacher": "Teacher", "capacity": 5, "room": "R1",
            "schedule": [[1, 1]] if schedule is None else schedule}


def _student(courses=None):
    return {"id": "S1", "name": "Student", "department": "D",
            "enrolled_courses": [] if courses is None else list(courses), "credit_limit": 18}


def _clock():
    # 合成鐘點，並非正式學校鐘點。
    return [{"period": period, "start": f"{8+i:02d}:00", "end": f"{8+i:02d}:45"}
            for i, period in enumerate(PERIODS)]


def _activity(activity_id="A1", start="08:10", end="08:30", day=WEEK):
    return {"id": activity_id, "name": "Activity " + activity_id,
            "start": day+"T"+start+"+08:00", "end": day+"T"+end+"+08:00"}


def _grid():
    return [[[] for period in range(12)] for day in range(7)]


def _item(item_id="C1", kind="course"):
    return {"kind": kind, "id": item_id, "name": ("Course " if kind == "course" else "Activity ")+item_id}


def _snapshot(grid=None, credits=None, activities=None):
    return {"week_start": WEEK, "grid": _grid() if grid is None else grid,
            "course_credits": {} if credits is None else credits,
            "activities": [] if activities is None else activities}


def _error(prefix, function, *args, **kwargs):
    before = deepcopy((args, kwargs))
    try:
        function(*args, **kwargs)
    except ValueError as error:
        assert str(error).startswith(prefix+": "), str(error)
    else:
        raise AssertionError("Expected "+prefix)
    assert (args, kwargs) == before, "Error path modified input"


def test_normal_empty_build_and_consumers():
    table = build_timetable({}, _student(), [], week_start=WEEK)
    assert table == _snapshot()
    assert query_timetable(table) == []
    assert summarize_timetable(table) == {
        "daily_class_periods": [0]*7, "weekly_credits": 0, "daily_gaps": [0]*7,
        "total_gaps": 0, "empty_periods": 84}
    assert find_free_periods(table, start=[1, 1], end=[7, "c"]) == [
        {"day": day, "periods": list(PERIODS)} for day in range(1, 8)]


def test_normal_multislot_overlap_sort_and_credits():
    courses = {"C2": _course("C2", credits=4),
               "C1": _course(schedule=[[3, "a"], [1, 1]])}
    table = build_timetable(courses, _student(["C2", "C1"]), [], week_start=WEEK)
    expected = _grid()
    expected[0][0] = [_item("C1"), _item("C2")]
    expected[2][9] = [_item("C1")]
    assert table == _snapshot(expected, {"C1": 3, "C2": 4})
    assert summarize_timetable(table) == {
        "daily_class_periods": [1, 0, 1, 0, 0, 0, 0], "weekly_credits": 7,
        "daily_gaps": [0]*7, "total_gaps": 0, "empty_periods": 82}


def test_normal_activity_mapping_and_exact_endpoints():
    gap = _activity("A", "08:45", "09:00")
    crossing = _activity("B", "08:44", "09:01")
    table = build_timetable({"C1": _course()}, _student(["C1"]), [crossing, gap],
                             week_start=WEEK, period_times=_clock())
    expected = _grid()
    expected[0][0] = [_item(), _item("B", "activity")]
    expected[0][1] = [_item("B", "activity")]
    assert table == _snapshot(expected, {"C1": 3}, [gap, crossing])


def test_normal_course_and_activity_id_are_separate():
    table = build_timetable({"C1": _course()}, _student(["C1"]), [_activity("C1")],
                             week_start=WEEK, period_times=_clock())
    assert table["grid"][0][0] == [_item("C1"), _item("C1", "activity")]
    assert query_timetable(table, course_id="C1") == [
        {"day": 1, "period": 1, "items": [_item("C1")]}]
    assert summarize_timetable(table)["weekly_credits"] == 3


def test_normal_query_and_conditions():
    courses = {"C1": _course(schedule=[[1, 1], [3, "a"]]), "C2": _course("C2")}
    table = build_timetable(courses, _student(["C1", "C2"]), [], week_start=WEEK)
    assert query_timetable(table, day=3, period="a", course_id="C1") == [
        {"day": 3, "period": "a", "items": [_item()]}]
    assert query_timetable(table, day=1, period="a", course_id="C1") == []
    assert query_timetable(table, day=3) == [{"day": 3, "period": "a", "items": [_item()]}]
    assert query_timetable(table, period=1) == [
        {"day": 1, "period": 1, "items": [_item("C1"), _item("C2")]}]


def test_normal_query_exact_ids_and_no_matches():
    table = build_timetable({"C1": _course()}, _student(["C1"]), [], week_start=WEEK)
    for course_id in ["missing", "c1", " C1", "C1 "]:
        assert query_timetable(table, course_id=course_id) == [], course_id
    assert query_timetable(table, day=7, period="c") == []


def test_normal_query_keeps_all_sorted_items():
    courses = {"C2": _course("C2"), "C1": _course()}
    activities = [_activity("B"), _activity("A")]
    table = build_timetable(courses, _student(["C2", "C1"]), activities,
                             week_start=WEEK, period_times=_clock())
    table["grid"][0][0].reverse()
    assert query_timetable(table) == [{
        "day": 1, "period": 1,
        "items": [_item("C1"), _item("C2"), _item("A", "activity"), _item("B", "activity")]}]


def test_normal_query_returns_independent_nested_objects():
    table = build_timetable({"C1": _course(schedule=[[1, 1], [1, 2]])},
                             _student(["C1"]), [], week_start=WEEK)
    before = deepcopy(table)
    result = query_timetable(table)
    assert table == before
    result[0]["items"][0]["name"] = "changed"
    result[0]["items"].append(_item("extra"))
    assert result[1]["items"] == [_item()]
    assert table == before
    table["grid"][0][1][0]["name"] = "source changed"
    assert result[1]["items"] == [_item()]


def test_normal_free_maximal_runs_and_truncated_range():
    table = build_timetable({"C1": _course(schedule=[[1, 2], [1, 7], [1, "b"]])},
                             _student(["C1"]), [], week_start=WEEK)
    expected = [{"day": 1, "periods": [3, 4, 5, 6]}, {"day": 1, "periods": [8, 9, "a"]}]
    assert find_free_periods(table, start=[1, 1], end=[1, "c"], min_periods=2) == expected
    assert find_free_periods(table, start=[1, 3], end=[1, "a"], min_periods=2) == expected


def test_normal_statistics_course_activity_boundaries():
    courses = {"C1": _course(schedule=[[1, 1], [2, 2]]),
               "C2": _course("C2", credits=4)}
    table = build_timetable(courses, _student(["C2", "C1"]), [_activity(start="12:00", end="12:30")],
                             week_start=WEEK, period_times=_clock())
    assert summarize_timetable(table) == {
        "daily_class_periods": [1, 1, 0, 0, 0, 0, 0], "weekly_credits": 7,
        "daily_gaps": [3, 0, 0, 0, 0, 0, 0], "total_gaps": 3, "empty_periods": 81}


def test_normal_activity_only_statistics():
    activities = [_activity("A", "08:00", "08:30"), _activity("B", "11:00", "11:30")]
    table = build_timetable({}, _student(), activities, week_start=WEEK, period_times=_clock())
    assert summarize_timetable(table) == {
        "daily_class_periods": [0]*7, "weekly_credits": 0, "daily_gaps": [2, 0, 0, 0, 0, 0, 0],
        "total_gaps": 2, "empty_periods": 82}


def test_normal_off_period_activity_retained_without_grid_items():
    activity = _activity(start="22:00", end="23:00")
    table = build_timetable({}, _student(), [activity], week_start=WEEK, period_times=_clock())
    assert table == _snapshot(activities=[activity])
    assert query_timetable(table) == []
    assert summarize_timetable(table)["empty_periods"] == 84
    assert find_free_periods(table, start=[1, 1], end=[1, "c"]) == [
        {"day": 1, "periods": list(PERIODS)}]


def test_normal_build_inputs_and_all_occupants_independent():
    courses = {"C1": _course(schedule=[[1, 1], [1, 2]])}
    student = _student(["C1"])
    activity = _activity(start="08:10", end="09:20")
    before = deepcopy((courses, student, activity))
    table = build_timetable(courses, student, [activity], week_start=WEEK, period_times=_clock())
    assert (courses, student, activity) == before
    assert len({id(row) for row in table["grid"]}) == 7
    assert len({id(cell) for row in table["grid"] for cell in row}) == 84
    items = [item for row in table["grid"] for cell in row for item in cell]
    assert len({id(item) for item in items}) == len(items)
    table["grid"][0][0][0]["name"] = "changed"
    assert table["grid"][0][1][0] == _item()
    table["activities"][0]["name"] = "metadata changed"
    assert table["grid"][0][1][1] == _item("A1", "activity")
    assert (courses, student, activity) == before
    courses["C1"]["name"] = "source changed"
    assert table["grid"][0][1][0] == _item()


def test_normal_core_pipeline_uses_f1_data_without_mutating_it():
    courses = {"C1": _course(schedule=[[1, 1], [3, 2]], credits=4)}
    student = _student(["C1"])
    activities = [_activity(start="10:00", end="10:30")]
    assert validate_course(courses["C1"]) is True
    assert validate_student(student, courses) is True
    before = deepcopy((courses, student, activities))
    checked = check_student_state(courses, {}, student, activities, [],
                                   week_start=WEEK, period_times=_clock())
    assert checked == {"week_start": WEEK, "issues": [],
                       "credits": {"before": 0, "after": 4, "limit": 18}}
    table = build_timetable(courses, student, activities, week_start=WEEK, period_times=_clock())
    assert query_timetable(table, course_id="C1") == [
        {"day": 1, "period": 1, "items": [_item()]},
        {"day": 3, "period": 2, "items": [_item()]}]
    assert find_free_periods(table, start=[1, 1], end=[1, 5], min_periods=2) == [
        {"day": 1, "periods": [4, 5]}]
    assert summarize_timetable(table) == {
        "daily_class_periods": [1, 0, 1, 0, 0, 0, 0], "weekly_credits": 4,
        "daily_gaps": [1, 0, 0, 0, 0, 0, 0], "total_gaps": 1, "empty_periods": 81}
    assert (courses, student, activities) == before


def test_boundary_cross_day_free_ranges_do_not_join():
    table = _snapshot()
    assert find_free_periods(table, start=[1, 9], end=[2, 2], min_periods=2) == [
        {"day": 1, "periods": [9, "a", "b", "c"]}, {"day": 2, "periods": [1, 2]}]
    assert find_free_periods(table, start=[1, 9], end=[2, 2], min_periods=5) == []


def test_boundary_nine_to_a_are_adjacent():
    assert find_free_periods(_snapshot(), start=[1, 9], end=[1, "a"], min_periods=2) == [
        {"day": 1, "periods": [9, "a"]}]


def test_boundary_single_endpoint_and_minimum_length():
    table = _snapshot()
    assert find_free_periods(table, start=[7, "c"], end=[7, "c"], min_periods=1) == [
        {"day": 7, "periods": ["c"]}]
    assert find_free_periods(table, start=[1, 1], end=[1, 2]) == []
    assert find_free_periods(table, start=[1, 1], end=[1, 3]) == [{"day": 1, "periods": [1, 2, 3]}]
    assert find_free_periods(table, start=[1, 1], end=[7, "c"], min_periods=13) == []


def test_boundary_all_grid_cells_occupied():
    schedule = [[day, period] for day in range(1, 8) for period in PERIODS]
    table = build_timetable({"C1": _course(schedule=schedule)}, _student(["C1"]), [], week_start=WEEK)
    assert find_free_periods(table, start=[1, 1], end=[7, "c"], min_periods=1) == []
    assert summarize_timetable(table) == {
        "daily_class_periods": [12]*7, "weekly_credits": 3, "daily_gaps": [0]*7,
        "total_gaps": 0, "empty_periods": 0}


def test_boundary_sunday_midnight_mapping():
    activity = _activity(start="19:30", end="19:40", day="2026-10-25")
    activity["end"] = "2026-10-26T00:00+08:00"
    table = build_timetable({}, _student(), [activity], week_start=WEEK, period_times=_clock())
    assert query_timetable(table) == [{"day": 7, "period": "c", "items": [_item("A1", "activity")]}]
    assert table["activities"] == [activity]


def test_boundary_one_occupied_cell_has_zero_gaps():
    table = build_timetable({"C1": _course(schedule=[[5, "c"]])},
                             _student(["C1"]), [], week_start=WEEK)
    assert summarize_timetable(table) == {
        "daily_class_periods": [0, 0, 0, 0, 1, 0, 0], "weekly_credits": 3,
        "daily_gaps": [0]*7, "total_gaps": 0, "empty_periods": 83}


def test_boundary_free_and_statistics_lists_independent():
    table = _snapshot()
    start, end = [1, 9], [2, 2]
    before = deepcopy((table, start, end))
    free = find_free_periods(table, start=start, end=end, min_periods=2)
    assert (table, start, end) == before
    free[0]["periods"].append("changed")
    assert free[1]["periods"] == [1, 2]
    first = summarize_timetable(table)
    second = summarize_timetable(table)
    first["daily_class_periods"][0] = 99
    assert first["daily_gaps"] == [0]*7 and second["daily_class_periods"] == [0]*7
    assert (table, start, end) == before


def test_error_build_missing_inputs_and_clock():
    for args in [(None, _student(), []), ({}, None, []), ({}, _student(), None)]:
        _error("MISSING_DATA", build_timetable, *args, week_start=WEEK)
    _error("MISSING_DATA", build_timetable, {}, _student(), [_activity()], week_start=WEEK)


def test_error_build_f1_models_and_references():
    for student in [{}, {**_student(), "enrolled_courses": ["missing"]},
                    {**_student(), "credit_limit": True}]:
        _error("INVALID_INPUT", build_timetable, {}, student, [], week_start=WEEK)
    course = _course()
    del course["teacher"]
    _error("INVALID_INPUT", build_timetable, {"C1": course}, _student(["C1"]), [], week_start=WEEK)


def test_error_query_condition_types_and_values():
    for key, values in {"day": [True, 0, 8, "1"], "period": [False, 0, 10, "1", "A"],
                        "course_id": [1, "", " "]}.items():
        for value in values:
            _error("INVALID_INPUT", query_timetable, _snapshot(), **{key: value})


def test_error_free_endpoint_types_order_and_minimum():
    table = _snapshot()
    for key in ["start", "end"]:
        for value in [None, [], (1, 1), [1], [True, 1], [1, True], [8, 1], [1, "A"], [1, 1.0]]:
            kwargs = {"start": [1, 1], "end": [7, "c"]}
            kwargs[key] = value
            _error("MISSING_DATA" if value is None else "INVALID_INPUT", find_free_periods,
                   table, **kwargs)
    for start, end in [([2, 1], [1, "c"]), ([1, "a"], [1, 9])]:
        _error("INVALID_INPUT", find_free_periods, table, start=start, end=end)
    for value in [None, True, False, 0, -1, 1.5, "3"]:
        _error("INVALID_INPUT", find_free_periods, table, start=[1, 1], end=[7, "c"], min_periods=value)


def test_error_snapshot_missing_required_fields():
    for function in [query_timetable, summarize_timetable]:
        _error("MISSING_DATA", function, None)
        _error("INVALID_INPUT", function, [])
        for field in ["week_start", "grid", "course_credits", "activities"]:
            table = _snapshot()
            del table[field]
            _error("INVALID_INPUT", function, table)
            table = _snapshot()
            table[field] = None
            _error("MISSING_DATA", function, table)


def test_error_full_grid_validated_outside_query_range():
    variants = [None, [], [[] for day in range(7)], _grid()]
    variants[-1][6][11] = {}
    for grid in variants:
        table = _snapshot()
        table["grid"] = grid
        prefix = "MISSING_DATA" if grid is None else "INVALID_INPUT"
        _error(prefix, query_timetable, table, day=1, period=1)
        _error(prefix, find_free_periods, table, start=[1, 1], end=[1, 3])
    for item in [None, [], {"kind": "other", "id": "A", "name": "N"},
                 {"kind": "course", "id": " ", "name": "N"},
                 {"kind": "course", "id": "C1", "name": ""}]:
        table = _snapshot()
        table["grid"][6][11] = [item]
        _error("INVALID_INPUT", query_timetable, table, day=1)
    table = _snapshot()
    table["grid"][0][0] = [_item(), _item()]
    _error("INVALID_INPUT", query_timetable, table)


def test_error_snapshot_course_credit_consistency():
    base = build_timetable({"C1": _course()}, _student(["C1"]), [], week_start=WEEK)
    for credits in [[], {}, {"extra": 3}, {"C1": 3, "extra": 4},
                    {"C1": True}, {"C1": 0}, {" ": 3}, {1: 3}]:
        table = deepcopy(base)
        table["course_credits"] = credits
        _error("INVALID_INPUT", summarize_timetable, table)
    table = deepcopy(base)
    table["grid"][0][1] = [{**_item(), "name": "different"}]
    _error("INVALID_INPUT", query_timetable, table)


def test_error_snapshot_activity_reference_and_day():
    activity = _activity()
    base = build_timetable({}, _student(), [activity], week_start=WEEK, period_times=_clock())
    for activities in [[], [_activity("other")], [activity, deepcopy(activity)]]:
        table = deepcopy(base)
        table["activities"] = activities
        _error("INVALID_INPUT", query_timetable, table)
    table = deepcopy(base)
    table["grid"][0][0][0]["name"] = "different"
    _error("INVALID_INPUT", query_timetable, table)
    table = deepcopy(base)
    table["grid"][1][0] = table["grid"][0][0]
    table["grid"][0][0] = []
    _error("INVALID_INPUT", query_timetable, table)


def test_error_snapshot_week_and_activity_range():
    table = _snapshot()
    table["week_start"] = "2026-10-20"
    _error("INVALID_INPUT", summarize_timetable, table)
    table = _snapshot(activities=[_activity(day="2026-10-26")])
    _error("OUT_OF_RANGE", query_timetable, table)


def load_tests(loader, tests, pattern):
    functions = [
        test_normal_empty_build_and_consumers, test_normal_multislot_overlap_sort_and_credits,
        test_normal_activity_mapping_and_exact_endpoints, test_normal_course_and_activity_id_are_separate,
        test_normal_query_and_conditions, test_normal_query_exact_ids_and_no_matches,
        test_normal_query_keeps_all_sorted_items, test_normal_query_returns_independent_nested_objects,
        test_normal_free_maximal_runs_and_truncated_range, test_normal_statistics_course_activity_boundaries,
        test_normal_activity_only_statistics, test_normal_off_period_activity_retained_without_grid_items,
        test_normal_build_inputs_and_all_occupants_independent, test_normal_core_pipeline_uses_f1_data_without_mutating_it,
        test_boundary_cross_day_free_ranges_do_not_join, test_boundary_nine_to_a_are_adjacent,
        test_boundary_single_endpoint_and_minimum_length, test_boundary_all_grid_cells_occupied,
        test_boundary_sunday_midnight_mapping, test_boundary_one_occupied_cell_has_zero_gaps,
        test_boundary_free_and_statistics_lists_independent, test_error_build_missing_inputs_and_clock,
        test_error_build_f1_models_and_references, test_error_query_condition_types_and_values,
        test_error_free_endpoint_types_order_and_minimum, test_error_snapshot_missing_required_fields,
        test_error_full_grid_validated_outside_query_range, test_error_snapshot_course_credit_consistency,
        test_error_snapshot_activity_reference_and_day, test_error_snapshot_week_and_activity_range,
    ]
    return unittest.TestSuite(unittest.FunctionTestCase(function) for function in functions)


if __name__ == "__main__":
    unittest.main()

