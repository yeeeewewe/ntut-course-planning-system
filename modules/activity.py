"""F4 活動管理、教室配置及報名。

活動以代號為鍵，採 F2 的起訖時間格式。每筆已配置活動另外保存
room（教室代號）及 participants（學號清單），即為占用及報名的來源。
"""

from copy import deepcopy as _deepcopy
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta

from .conflict import (
    check_activity_participation as _check_activity_participation,
    check_room_time_conflicts as _check_room_time_conflicts,
)


_INPUT_FIELDS = {"id", "name", "start", "end", "capacity", "type", "required_equipment"}


def _check_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}必須是非空白文字")


def _check_equipment(equipment, label):
    if not isinstance(equipment, list):
        raise ValueError(f"{label}必須是設備名稱清單")
    for item in equipment:
        _check_text(item, "設備名稱")
    if len(set(equipment)) != len(equipment):
        raise ValueError(f"{label}不得有重複設備")


def _activity_week(activity):
    """驗證活動輸入，回傳起始日期所在的星期一。"""
    if not isinstance(activity, dict) or activity.keys() != _INPUT_FIELDS:
        raise ValueError("活動資料須提供「代號、名稱、起訖時間、人數上限、類型、必要設備」")
    for field, label in (("id", "活動代號"), ("name", "活動名稱"), ("type", "活動類型")):
        _check_text(activity[field], label)
    if type(activity["capacity"]) is not int or activity["capacity"] < 1:
        raise ValueError("活動人數上限必須是正整數")
    _check_equipment(activity["required_equipment"], "必要設備")

    moments = []
    for field in ("start", "end"):
        value = activity[field]
        try:
            moment = _datetime.fromisoformat(value)
        except (ValueError, TypeError):
            raise ValueError("活動日期與時間必須有效，格式為 YYYY-MM-DDTHH:MM+08:00") from None
        if not value.endswith("+08:00") or moment.isoformat(timespec="minutes") != value:
            raise ValueError("活動日期與時間格式須為 YYYY-MM-DDTHH:MM+08:00")
        moments.append(moment)
    start, end = moments
    if start >= end:
        raise ValueError("開始時間必須早於結束時間")
    if start.date() != end.date() and (
        (end.date() - start.date()).days != 1 or end.hour != 0 or end.minute != 0
    ):
        raise ValueError("活動須在同一天內，結束時間可填次日 00:00")
    day = start.date()
    return (day - _timedelta(days=day.weekday())).isoformat()


def _week_activities(activities, week_start=None):
    if not isinstance(activities, dict):
        raise ValueError("活動集合須以活動代號為鍵")
    if week_start is None:
        return list(activities.values())
    try:
        start = _date.fromisoformat(week_start)
        end = (start + _timedelta(days=7)).isoformat()
    except (TypeError, ValueError, OverflowError):
        raise ValueError("週起始日須為有效的 YYYY-MM-DD 星期一") from None
    if start.isoformat() != week_start or start.weekday() != 0:
        raise ValueError("週起始日須為有效的 YYYY-MM-DD 星期一")
    return [
        item for item in activities.values() if week_start <= item["start"][:10] < end
    ]


def _get_activity(activities, activity_id):
    _check_text(activity_id, "活動代號")
    if not isinstance(activities, dict):
        raise ValueError("活動集合須以活動代號為鍵")
    if activity_id not in activities:
        raise ValueError(f"活動 {activity_id} 不存在")
    return activities[activity_id]


def _room_capacity(classrooms, room_id):
    if not isinstance(classrooms, dict):
        raise ValueError("教室集合須以教室代號為鍵")
    room = classrooms.get(room_id)
    if not isinstance(room, dict) or room.get("id") != room_id:
        raise ValueError(f"教室 {room_id} 不存在或代號資料不符")
    capacity = room.get("capacity")
    if type(capacity) is not int or capacity < 1:
        raise ValueError(f"教室 {room_id} 的容量必須是正整數")
    return capacity


def _conflict_description(issue, activity_id):
    others = [
        *(f"課程 {code}" for code in issue["course_ids"]),
        *(f"活動 {code}" for code in issue["activity_ids"] if code != activity_id),
    ]
    return "時段與" + "、".join(others) + "重疊"


def find_available_rooms(activities, courses, classrooms, activity, *, period_times):
    """回傳可用教室代號及各未通過教室的原因。同代號舊占用視為待替換。"""
    week_start = _activity_week(activity)
    if not isinstance(classrooms, dict):
        raise ValueError("教室集合須以教室代號為鍵")
    activity_id = activity["id"]
    booked = [
        item for item in _week_activities(activities, week_start) if item["id"] != activity_id
    ]
    if period_times is None:
        raise ValueError("缺少鐘點表，須提供第 1～9 節及 a、b、c 節的開始、結束時間")

    available = []
    rejected = {}
    for room_id in classrooms:
        _check_text(room_id, "教室代號")
        capacity = _room_capacity(classrooms, room_id)
        equipment = classrooms[room_id].get("equipment", [])
        _check_equipment(equipment, f"教室 {room_id} 的設備")
        reasons = []
        if capacity < activity["capacity"]:
            reasons.append(f"容量 {capacity} 小於預計人數 {activity['capacity']}")
        missing = [item for item in activity["required_equipment"] if item not in equipment]
        if missing:
            reasons.append("缺少設備 " + "、".join(missing))

        candidate = dict(activity, room=room_id)
        result = _check_room_time_conflicts(
            courses, [*booked, candidate], week_start=week_start, period_times=period_times,
        )
        for issue in result["issues"]:
            if activity_id in issue["activity_ids"]:
                reason = _conflict_description(issue, activity_id)
                if reason not in reasons:
                    reasons.append(reason)
        if reasons:
            rejected[room_id] = reasons
        else:
            available.append(room_id)
    available.sort(key=lambda room_id: (classrooms[room_id]["capacity"], room_id))
    return {"available_rooms": available, "rejected_rooms": rejected}


def _choose_room(result, preferred=None):
    available = result["available_rooms"]
    if preferred in available:
        return preferred
    if available:
        return available[0]
    rejected = result["rejected_rooms"]
    details = "\n".join(f"{room}：{'；'.join(rejected[room])}" for room in sorted(rejected))
    raise ValueError("無可用教室\n" + (details or "目前沒有教室資料"))


def add_activity(activities, courses, classrooms, activity, *, period_times):
    """配置教室後新增活動，回傳獨立的已配置活動資料。"""
    if not isinstance(activities, dict):
        raise ValueError("活動集合須以活動代號為鍵")
    activity_id = activity.get("id") if isinstance(activity, dict) else None
    _check_text(activity_id, "活動代號")
    if activity_id in activities:
        raise ValueError(f"活動代號 {activity_id} 已存在")
    result = find_available_rooms(activities, courses, classrooms, activity, period_times=period_times)
    room = _choose_room(result)
    stored = _deepcopy(dict(activity, room=room, participants=[]))
    activities[activity_id] = stored
    return _deepcopy(stored)


def _check_participant(activities, courses, students, student_id, activity, *, period_times):
    if not isinstance(students, dict):
        raise ValueError("學生集合須以學號為鍵")
    student = students.get(student_id)
    if not isinstance(student, dict) or student.get("id") != student_id:
        raise ValueError(f"學生 {student_id} 不存在或學號資料不符")
    day = _date.fromisoformat(activity["start"][:10])
    week_start = (day - _timedelta(days=day.weekday())).isoformat()
    others = [
        item for item in _week_activities(activities, week_start) if item["id"] != activity["id"]
    ]
    result = _check_activity_participation(
        courses, student, [item for item in others if student_id in item["participants"]],
        activity, [item for item in others if item["room"] == activity["room"]],
        week_start=week_start, period_times=period_times,
    )
    if result["issues"]:
        details = "；".join(dict.fromkeys(
            _conflict_description(issue, activity["id"]) for issue in result["issues"]
        ))
        raise ValueError(f"學生 {student_id} 無法參加：{details}")


def update_activity(activities, activity_id, changes, courses, classrooms, students, *, period_times):
    """修改活動資料，重新配置場地，改期前確認已報名者可以參加。"""
    current = _get_activity(activities, activity_id)
    if not isinstance(changes, dict) or not changes or changes.keys() - (_INPUT_FIELDS - {"id"}):
        raise ValueError("請提供要修改的活動欄位，活動代號、教室及報名名單由系統管理")
    activity = {field: current[field] for field in _INPUT_FIELDS}
    activity.update(changes)
    result = find_available_rooms(activities, courses, classrooms, activity, period_times=period_times)
    room = _choose_room(result, preferred=current["room"])
    participants = current["participants"]
    if len(participants) > activity["capacity"]:
        raise ValueError(f"活動人數上限不可低於目前報名的 {len(participants)} 人")
    stored = _deepcopy(dict(activity, room=room, participants=participants))
    if (current["start"], current["end"]) != (stored["start"], stored["end"]):
        for student_id in participants:
            _check_participant(activities, courses, students, student_id, stored, period_times=period_times)
    activities[activity_id] = stored
    return _deepcopy(stored)


def cancel_activity(activities, activity_id):
    """取消指定活動，刪除該筆活動及報名名單，並回傳原活動的副本。"""
    canceled = _deepcopy(_get_activity(activities, activity_id))
    del activities[activity_id]
    return canceled


def search_activities(activities, *, activity_id=None, student_id=None, week_start=None):
    """依活動代號、學號與週起始日查詢有效活動，回傳依代號排序的副本。"""
    if activity_id is not None:
        _check_text(activity_id, "活動代號")
    if student_id is not None:
        _check_text(student_id, "學生學號")
    records = _week_activities(activities, week_start)
    matches = [
        item for item in records
        if (activity_id is None or item["id"] == activity_id)
        and (student_id is None or student_id in item["participants"])
    ]
    return _deepcopy(sorted(matches, key=lambda item: item["id"]))


def register_for_activity(activities, activity_id, student_id, courses, classrooms, students, *, period_times):
    """報名活動，成功後回傳包含新報名名單的活動副本。"""
    activity = _get_activity(activities, activity_id)
    _check_text(student_id, "學生學號")
    participants = activity["participants"]
    if student_id in participants:
        raise ValueError(f"學生 {student_id} 已報名此活動")
    room_capacity = _room_capacity(classrooms, activity["room"])
    if len(participants) >= min(activity["capacity"], room_capacity):
        raise ValueError(f"活動已額滿（活動上限 {activity['capacity']} 人，教室容量 {room_capacity} 人）")
    _check_participant(activities, courses, students, student_id, activity, period_times=period_times)
    participants.append(student_id)
    return _deepcopy(activity)
