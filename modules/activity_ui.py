"""F4 校園活動與教室配置的文字操作介面。"""

from .activity import (
    add_activity, cancel_activity, find_available_rooms, register_for_activity,
    search_activities, update_activity,
)
from .period_times import default_period_times


def input_activity(read_input, activity_id, current=None):
    """修改時空白保留原值，設備輸入 - 可清空。"""
    def value(prompt, old=""):
        entered = read_input(prompt).strip()
        return entered or old

    def time_value(prompt, field):
        entered = value(prompt, current.get(field, "")[11:16].replace(":", ""))
        if (len(entered) != 4 or not entered.isascii() or not entered.isdigit()
                or int(entered[:2]) > 23 or int(entered[2:]) > 59):
            raise ValueError("時間請輸入四位數 HHMM，例如 0800；小時須為 00～23，分鐘須為 00～59")
        return entered[:2] + ":" + entered[2:]

    current = current or {}
    name = value("活動名稱：", current.get("name", ""))
    day = value("日期（YYYY-MM-DD）：", current.get("start", "")[:10])
    start = time_value("開始時間（HHMM，例如 0800）：", "start")
    end = time_value("結束時間（HHMM，例如 0900，同日）：", "end")
    capacity = int(value("預計人數／報名上限：", str(current.get("capacity", ""))))
    kind = value("活動類型：", current.get("type", ""))
    equipment = value("所需設備（以逗號分隔，- 表示無）：",
                      ",".join(current.get("required_equipment", [])))
    return dict(id=activity_id, name=name, start=f"{day}T{start}+08:00",
                end=f"{day}T{end}+08:00", capacity=capacity, type=kind,
                required_equipment=[] if equipment in ("", "-") else
                [item.strip() for item in equipment.replace("，", ",").split(",")])


def display_activity(activity, classrooms):
    room = activity["room"]
    print(f"{activity['id']} {activity['name']}（{activity['type']}） "
          f"{activity['start'][:10]} {activity['start'][11:16]}～{activity['end'][11:16]} "
          f"教室：{room} 報名：{len(activity['participants'])}/{activity['capacity']} "
          f"教室容量：{classrooms[room]['capacity']}")
    print("設備需求：" + ("、".join(activity["required_equipment"]) or "無"))


def activity_action(choice, activities, courses, classrooms, students, read_input, *, period_times):
    if choice == "4":
        records = search_activities(
            activities, activity_id=read_input("活動代號（留空查全部）：") or None,
            student_id=read_input("學生學號（留空不限）：") or None,
            week_start=read_input("週起始日（YYYY-MM-DD 星期一，留空不限）：") or None,
        )
        if not records:
            print("查無符合條件的活動。")
        for record in records:
            display_activity(record, classrooms)
        return

    activity_id = read_input("活動代號：").strip()
    if choice == "1":
        record = add_activity(activities, courses, classrooms,
                              input_activity(read_input, activity_id), period_times=period_times)
        print("活動新增成功。")
    elif choice == "2":
        cancel_activity(activities, activity_id)
        print("活動已取消，教室與報名名單已釋放。")
        return
    elif choice == "3":
        matches = search_activities(activities, activity_id=activity_id)
        if not matches:
            raise ValueError(f"活動 {activity_id} 不存在")
        print("空白保留原值；設備輸入 - 可清空。")
        changes = input_activity(read_input, activity_id, matches[0])
        del changes["id"]
        record = update_activity(activities, activity_id, changes, courses, classrooms,
                                 students, period_times=period_times)
        print("活動修改成功。")
    elif choice == "5":
        record = register_for_activity(activities, activity_id, read_input("學生學號：").strip(),
                                       courses, classrooms, students, period_times=period_times)
        print("報名成功。")
    elif choice == "6":
        result = find_available_rooms(activities, courses, classrooms,
                                      input_activity(read_input, activity_id), period_times=period_times)
        print("可用教室：" + ("、".join(result["available_rooms"]) or "無合適教室"))
        for room, reasons in result["rejected_rooms"].items():
            print(f"{room}：{'；'.join(reasons)}")
        return
    else:
        raise ValueError("請輸入合法選項")
    display_activity(record, classrooms)


def activity_menu(activities, courses, classrooms, students, read_input, show_menu, period_times):
    options = ["新增活動", "取消活動", "修改活動", "查詢活動", "活動報名", "篩選場地"]
    print("活動與報名資料僅保留於本次程式執行期間。")
    while True:
        show_menu(options, current_function="校園活動與教室配置")
        choice = read_input("請輸入選項（0 返回主選單）：")
        if choice == "0":
            return
        try:
            if choice not in tuple("123456"):
                raise ValueError("請輸入合法選項")
            if choice in ("1", "3", "5", "6") and not period_times:
                period_times.extend(default_period_times())
            activity_action(choice, activities, courses, classrooms, students, read_input,
                            period_times=period_times)
        except (ValueError, TypeError, KeyError) as error:
            print(f"操作失敗：{error}")
        read_input("按 Enter 繼續")
