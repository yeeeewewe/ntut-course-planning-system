from course.py import validate_course
def getcurriculum():
    curriculum = [[0] * 7 for k in range(12)]    # 12列7行的二維陣列(空課表)
    return curriculum
def getL(schedule):
    L=len(schedule)
    return L
def getindex(schedule,k):
    Day=['1','2','3','4','5','6','7']
    Section=['1','2','3','4','5','6','7','8','9','a','b','c']
    L=getL(schedule)
    for i in range(k,L):
        index_D=Day.index(schedule[i][0])
        index_S=Section.index(schedule[i][1])
        return i,index_D,index_S
def getRoom_curriculum(id, schedule):
    curriculum=getcurriculum()
    L=getL(schedule)
    k=0
    for i in range(L):
        k,index_D,index_S=getindex(schedule,k)
        k+=1
        curriculum[index_D][index_S]=id
    return curriculum