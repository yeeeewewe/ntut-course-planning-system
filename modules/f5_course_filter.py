from typing import List, Dict, Tuple, Set, Optional

# 定義合法的星期與節次常數（僅作為驗證規則常數，非系統狀態資料）
VALID_DAYS = {1, 2, 3, 4, 5, 6, 7}
VALID_PERIODS = {'1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c'}
PERIOD_ORDER = {p: idx for idx, p in enumerate(['1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c'])}


def format_slot(slot: Tuple[int, str]) -> str:
    """將 (星期, 節次) 格式化為易讀字串，例如 (1, 'a') -> '星期1第a節'"""
    day, period = slot
    return f"星期{day}第{period}節"


def sort_slots(slots: Set[Tuple[int, str]]) -> List[Tuple[int, str]]:
    """依 F2 規範：依星期及節次排序時段"""
    return sorted(list(slots), key=lambda s: (s[0], PERIOD_ORDER.get(s[1], 99)))


def find_slot_conflicts(slots_a: List[Tuple[int, str]], slots_b: Set[Tuple[int, str]]) -> List[Tuple[int, str]]:
    """
    共用時段衝突檢查函式（可供 F2, F4, F5 共用）
    回傳重疊的時段列表（已排序）
    """
    overlap = set(slots_a).intersection(slots_b)
    return sort_slots(overlap)


def filter_and_check_courses(
    courses: List[Dict],
    student_prefs: Dict,
    existing_enrollments: Optional[List[str]] = None
) -> Dict:
    """
    F5. 多條件課程篩選與可行性檢查
    
    參數:
        courses: 課程資料列表（符合 F1 資料結構）
        student_prefs: 學生篩選條件字典，包含:
            - desired_courses (List[str]): 希望修習的課程代號
            - required_courses (List[str]): 必修清單課程代號
            - min_credits (int): 最低學分
            - max_credits (int): 最高學分
            - unavailable_slots (List[Tuple[int, str]]): 不可上課時段，如 [(1, '1'), (3, 'a')]
            - preferred_days (List[int]): 偏好的上課星期，如 [1, 3, 5]
        existing_enrollments: 學生目前已選課程代號（可選，預設為空）
        
    回傳:
        Dict: 包含 is_feasible (bool), candidates (List[Dict]), errors (List[str]), warnings (List[str]), summary (Dict)
    """
    if existing_enrollments is None:
        existing_enrollments = []

    desired_ids: Set[str] = set(student_prefs.get("desired_courses", []))
    required_ids: Set[str] = set(student_prefs.get("required_courses", []))
    enrolled_ids: Set[str] = set(existing_enrollments)
    
    # 目標查詢聯集（必修 + 希望修習 + 已選）
    target_ids: Set[str] = desired_ids.union(required_ids).union(enrolled_ids)

    min_credits: int = student_prefs.get("min_credits", 0)
    max_credits: int = student_prefs.get("max_credits", 99)
    unavailable_slots: Set[Tuple[int, str]] = set(student_prefs.get("unavailable_slots", []))
    preferred_days: Set[int] = set(student_prefs.get("preferred_days", []))

    course_map: Dict[str, Dict] = {c["course_id"]: c for c in courses}
    candidates: List[Dict] = []
    errors: List[str] = []
    warnings: List[str] = []

    # 1. 檢查輸入條件本身的合法性與矛盾
    if min_credits < 0 or max_credits < 0:
        errors.append("輸入錯誤：最低或最高學分不可為負數。")
    if min_credits > max_credits:
        errors.append(f"條件矛盾：最低學分 ({min_credits}) 大於最高學分 ({max_credits})。")

    for day, period in unavailable_slots:
        if day not in VALID_DAYS or period not in VALID_PERIODS:
            errors.append(f"輸入錯誤：無效的不可上課時段 ({day}, '{period}')。")

    # 2. 逐一檢查目標課程
    for cid in sorted(list(target_ids)):
        if cid not in course_map:
            msg = f"查無課程代號：{cid}"
            if cid in required_ids or cid in enrolled_ids:
                errors.append(f"必修/已選異常：{msg}")
            else:
                warnings.append(msg)
            continue

        course = course_map[cid]
        is_req = (cid in required_ids) or (cid in enrolled_ids)

        # 檢查 A: 課程是否已額滿（若不在已選名單中才檢查名額）
        if cid not in enrolled_ids and course["enrolled"] >= course["capacity"]:
            msg = f"課程「{course['name']} ({cid})」已額滿 ({course['enrolled']}/{course['capacity']})。"
            if is_req:
                errors.append(f"條件矛盾（必修額滿）：{msg}")
            else:
                warnings.append(f"已排除選修：{msg}")
            continue

        # 檢查 B: 是否與不可上課時段衝突
        conflicts = find_slot_conflicts(course["slots"], unavailable_slots)
        if conflicts:
            conflict_str = "、".join(format_slot(s) for s in conflicts)
            msg = f"課程「{course['name']} ({cid})」與不可上課時段（{conflict_str}）衝突。"
            if is_req:
                errors.append(f"條件矛盾（必修與禁用時段衝突）：{msg}")
            else:
                warnings.append(f"已排除選修：{msg}")
            continue

        # 計算偏好星期符合度
        course_days = {slot[0] for slot in course["slots"]}
        matched_days = course_days.intersection(preferred_days)
        # 計算該課程有多少比例的上課天數落在偏好星期內
        pref_ratio = len(matched_days) / len(course_days) if course_days else 0.0

        candidates.append({
            **course,
            "is_required": is_req,
            "pref_day_ratio": pref_ratio
        })

    # 3. 檢查必修（含已選）課程之間是否互相衝堂
    req_candidates = [c for c in candidates if c["is_required"]]
    occupied_slots: Dict[Tuple[int, str], Dict] = {}
    
    for rc in req_candidates:
        for slot in sort_slots(set(rc["slots"])):
            if slot in occupied_slots:
                prev_course = occupied_slots[slot]
                errors.append(
                    f"條件矛盾（必修互衝）：「{prev_course['name']} ({prev_course['course_id']})」與"
                    f"「{rc['name']} ({rc['course_id']})」在 {format_slot(slot)} 衝堂。"
                )
            else:
                occupied_slots[slot] = rc

    # 4. 檢查學分上下限可行性
    req_credits = sum(c["credits"] for c in req_candidates)
    total_candidate_credits = sum(c["credits"] for c in candidates)

    if req_credits > max_credits:
        errors.append(f"條件矛盾：必修總學分 ({req_credits}) 已超過最高學分限制 ({max_credits})。")

    if total_candidate_credits < min_credits:
        errors.append(
            f"無法滿足最低學分：符合條件之候選課程總學分僅 {total_candidate_credits} 學分，"
            f"低於最低要求 ({min_credits} 學分)。"
        )

    # 5. 排序候選課程：必修優先 -> 偏好星期符合比例高者優先 -> 課程代號排序
    candidates.sort(key=lambda c: (not c["is_required"], -c["pref_day_ratio"], c["course_id"]))

    return {
        "is_feasible": len(errors) == 0,
        "candidates": candidates,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "required_credits": req_credits,
            "max_possible_credits": total_candidate_credits,
            "min_credits_required": min_credits,
            "max_credits_allowed": max_credits
        }
    }