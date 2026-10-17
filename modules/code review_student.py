print("===開始執行student module測試===")

my_students = {}
my_courses = {
    "CS101": {
        "id": "CS101", "name": "基礎程式設計", "credits": 3, "required": True,
        "teacher": "張教授", "capacity": 50, "room": "R101", "schedule": [[1, 2]]
    }
}

# 測試1: 準備一筆完全合法的假學生資料，測試能否成功新增
dummy_student_1 = {
    "id": "115590123",
    "name": "阿金",
    "department": "資工系",
    "enrolled_courses": ["CS101"], 
    "credit_limit": 25
}

result_add_1 = add_student(my_students, dummy_student_1, my_courses)
print(f"(checked) 測試1 (新增合法學生): {'成功' if result_add_1 else '失敗'}")

# 測試2: 嘗試新增學號重複的學生(防呆測試)
dummy_student_2 = dummy_student_1.copy()
dummy_student_2["name"] = "複製人阿金" 
result_add_2 = add_student(my_students, dummy_student_2, my_courses)
if not result_add_2:
    print("(checked) 測試2 (新增重複學號): 系統成功擋下！防呆邏輯正確")
else:
    print("(bug!) 測試2 (新增重複學號): 允許學號重複，有bug！")

# 測試3: 嘗試新增一個選了「不存在的課 (Ghost101)」的學生
# 預期結果：因為課程庫裡面沒有 Ghost101，系統必須拒絕這個學生資料！
dummy_student_3 = {
    "id": "115590456",
    "name": "小睿",
    "department": "電機系",
    "enrolled_courses": ["Ghost101"],
    "credit_limit": 25
}
result_add_3 = add_student(my_students, dummy_student_3, my_courses)
if not result_add_3:
    print("(checked) 測試3 (選修幽靈課程): 系統成功擋下！跨資料庫檢查防護完美")
else:
    print("(bug!) 測試3 (選修幽靈課程): 完蛋了，系統讓學生選了不存在的課！有 Bug！")

# 測試4: 測試修改功能：幫阿金改名字，但其他資料不變
result_update = update_student(my_students, "115590123", {"name": "阿白"}, my_courses)
if result_update and my_students["115590123"]["name"] == "阿白":
    print("(checked) 測試4 (修改學生資料): 成功修改學生姓名！")
else:
    print("(bug!) 測試4 (修改學生資料): 修改失敗或未正確儲存！")

print("===學生模組測試腳本執行完畢===")