"""F3 個人課表與空閒時段的文字操作介面。"""

from datetime import date, timedelta
from unicodedata import east_asian_width
from .timetable import build_timetable, query_timetable, find_free_periods, summarize_timetable


PERIODS = [1, 2, 3, 4, 5, 6, 7, 8, 9, "a", "b", "c"]
WEEKDAYS = "一二三四五六日"


def input_slot(read_input, prompt):
    value = read_input(prompt).strip().lower()
    if len(value) != 2 or value[0] not in "1234567" or value[1] not in "123456789abc":
        raise ValueError("時段格式必須為星期加節次，例如 11、1c、52；星期為 1～7，節次為 1～9 或 a、b、c")
    return [int(value[0]), int(value[1]) if value[1].isdigit() else value[1]]


def slot_index(slot):
    return (slot[0] - 1) * 12 + PERIODS.index(slot[1])


def input_range(read_input):
    start = input_slot(read_input, "起始時段（例如 1c）：")
    end = input_slot(read_input, "結尾時段（例如 52）：")
    if slot_index(start) > slot_index(end):
        raise ValueError("起始時段不可晚於結尾時段")
    return start, end


def describe_items(items):
    return "／".join(
        f"[{'課程' if item['kind'] == 'course' else '活動'}] {item['id']} {item['name']}"
        for item in items
    ) or "空閒"


def display_timetable(timetable):
    print("每週課表")
    rows = [["節次"] + [f"星期{day}" for day in WEEKDAYS]]
    for period_index, period in enumerate(PERIODS):
        rows.append([str(period)] + [
            "/".join(item["id"] for item in timetable["grid"][day][period_index]) or "空閒"
            for day in range(7)
        ])

    def text_width(value):
        return sum(2 if east_asian_width(char) in ("W", "F") else 1 for char in value)

    widths = [max(text_width(row[column]) for row in rows) for column in range(8)]
    for row in rows:
        print(" | ".join(value + " " * (width - text_width(value))
                         for value, width in zip(row, widths)))
    if timetable["activities"]:
        print("個人活動（含未落在上課節次內的活動）：")
        for activity in timetable["activities"]:
            day = date.fromisoformat(activity["start"][:10]).weekday()
            print(f"{activity['id']} {activity['name']}：星期{WEEKDAYS[day]} "
                  f"{activity['start'][11:16]} ～ {activity['end'][11:16]}")


def timetable_action(choice, timetable, read_input):
    if choice == "1":
        display_timetable(timetable)
    elif choice == "2":
        start, end = input_range(read_input)
        course_id = read_input("課程代號（留空不限）：") or None
        results = query_timetable(timetable, course_id=course_id)
        occupied = {(item["day"], item["period"]): item["items"] for item in results}
        print(f"查詢範圍：星期{WEEKDAYS[start[0] - 1]}第{start[1]}節"
              f"到星期{WEEKDAYS[end[0] - 1]}第{end[1]}節（包含起訖時段）")
        found = False
        for index in range(slot_index(start), slot_index(end) + 1):
            day_index, period_index = divmod(index, 12)
            period = PERIODS[period_index]
            items = occupied.get((day_index + 1, period), [])
            if course_id and not items:
                continue
            found = True
            print(f"星期{WEEKDAYS[day_index]} 第{period}節：" + describe_items(items))
        if not found:
            print("查無符合條件的時段。")
    elif choice == "3":
        start, end = input_range(read_input)
        minimum = read_input("最少連續空閒節數（留空為 3）：")
        results = find_free_periods(
            timetable, start=start, end=end,
            min_periods=int(minimum) if minimum else 3,
        )
        print("空閒時段依每日分開計算，不跨日合併。")
        if not results:
            print("查無符合條件的連續空閒時段。")
        for result in results:
            print(f"星期{WEEKDAYS[result['day'] - 1]}："
                  + "、".join(f"第{period}節" for period in result["periods"])
                  + f"（連續 {len(result['periods'])} 節）")
    elif choice == "4":
        summary = summarize_timetable(timetable)
        for day in range(7):
            print(f"星期{WEEKDAYS[day]}：上課 {summary['daily_class_periods'][day]} 節，"
                  f"空堂 {summary['daily_gaps'][day]} 節")
        print(f"每週總學分：{summary['weekly_credits']}")
        print(f"每週空堂數：{summary['total_gaps']}（每日首末占用時段之間的空格）")
        print(f"全週空閒節數：{summary['empty_periods']}")


def timetable_menu(courses, students, read_input, show_menu):
    student_id = read_input("請輸入學號（留空返回主選單）：")
    if not student_id:
        return
    if student_id not in students:
        raise ValueError(f"學生 {student_id} 不存在")
    # 核心活動模型需要日期，以固定星期一作為內部換算基準；介面僅使用星期與節次。
    week_start = "2000-01-03"
    activities = []
    period_times = None
    timetable = build_timetable(courses, students[student_id], activities, week_start=week_start)
    options = ["顯示每週課表", "查詢課表", "查詢連續空閒時段", "課表統計", "加入本次查詢的個人活動"]
    while True:
        show_menu(options, current_function=f"個人課表產生－{student_id}")
        choice = read_input("請輸入選項（0 返回主選單）：")
        if choice == "0":
            return
        try:
            if choice in ("1", "2", "3", "4"):
                timetable_action(choice, timetable, read_input)
            elif choice == "5":
                activity_id = read_input("活動代號：")
                name = read_input("活動名稱：")
                day = int(read_input("活動星期（1～7）："))
                if not 1 <= day <= 7:
                    raise ValueError("活動星期必須為 1～7")
                activity_day = (date.fromisoformat(week_start) + timedelta(days=day - 1)).isoformat()
                start = read_input("開始時間（HH:MM）：")
                end = read_input("結束時間（HH:MM，同日）：")
                candidate = {"id": activity_id, "name": name,
                             "start": f"{activity_day}T{start}+08:00",
                             "end": f"{activity_day}T{end}+08:00"}
                clock = period_times
                if clock is None:
                    print("首次加入活動，請設定 12 個節次的實際鐘點，以對應活動占用時段。")
                    clock = [{"period": period,
                              "start": read_input(f"第{period}節開始時間（HH:MM）："),
                              "end": read_input(f"第{period}節結束時間（HH:MM）：")}
                             for period in PERIODS]
                built = build_timetable(courses, students[student_id], [*activities, candidate],
                                        week_start=week_start, period_times=clock)
                activities.append(candidate)
                period_times = clock
                timetable = built
                print("已加入個人活動並更新課表，活動僅保留於本次課表查詢。")
            else:
                raise ValueError("請輸入合法選項")
        except (ValueError, TypeError, KeyError) as error:
            print(f"操作失敗：{error}")
        read_input("按 Enter 繼續")
