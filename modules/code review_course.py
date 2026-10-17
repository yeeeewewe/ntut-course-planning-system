print("===開始執行course module測試===")

my_courses = {}
my_students = {}

# 測試1: 準備一筆完全合法的假課程資料，測試能否成功新增
dummy_course = {
    "id": "CS101",
    "name": "基礎程式設計",
    "credits": 3,
    "required": True,
    "teacher": "張教授",
    "capacity": 50,
    "room": "R101",
    "schedule": [[1, 2], [1, 3]] 
}

result_add = add_course(my_courses, dummy_course)
print(f"(checked) 測試1 (新增合法課程): {'成功' if result_add else '失敗'}")

# 測試2: 準備一筆極端的「假學生資料」，讓他選修剛剛的 CS101
my_students["115590123"] = {
    "student_id": "115590123",
    "name": "阿金",
    "enrolled_courses": ["CS101"] 
}
print(f"(checked) 測試2 (情境設定): 學生(115590123) 已經選修了課程(CS101)")

# 測試3:嘗試刪除「已經有人選修」的課程
# 預期結果：系統必須拒絕request
result_delete_fail = delete_course(my_courses, "CS101", my_students)
if not result_delete_fail:
    print("(checked) 測試3 (刪除有人選的課): 系統成功擋下！程式邏輯正確")
else:
    print("(bug!) 測試3 (刪除有人選的課): 課程被系統刪除了！有bug!")

# 測試4: 新增另一堂「無人選修」的課並嘗試刪除
dummy_course_2 = dummy_course.copy()
dummy_course_2["id"] = "PE101"
add_course(my_courses, dummy_course_2) 

result_delete_success = delete_course(my_courses, "PE101", my_students)
if result_delete_success:
    print("(checked) 測試4 (刪除沒人選的課): 成功刪除！程式邏輯正確")
else:
    print("(bug!) 測試4 (刪除沒人選的課): 系統錯誤擋下，有bug！")

print("===測試腳本執行完畢===")