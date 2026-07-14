from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from app.db import db
from app.routers.auth_router import get_current_user
from pydantic import BaseModel

router = APIRouter()

class UserProgressRequest(BaseModel):
    completed: bool

@router.get("")
async def get_courses(isPopular: Optional[bool] = None, courseType: Optional[str] = None):
    where_clause = {}
    if isPopular is not None:
        where_clause["isPopular"] = isPopular
    if courseType is not None:
        where_clause["courseType"] = courseType
        
    courses = await db.course.find_many(
        where=where_clause if where_clause else None,
        include={"lessons": True}
    )
    # Return courses with basic information
    return courses

@router.get("/{course_id}")
async def get_course_details(course_id: str, user_token: Optional[str] = None):
    # Determine the user
    user = None
    if user_token:
        # Resolve user manually to avoid crashing if token is invalid or guest
        try:
            from jose import jwt
            import os
            JWT_SECRET = os.getenv("JWT_SECRET", "gordon_jwt_secret_key_extremely_secure_12345")
            payload = jwt.decode(user_token, JWT_SECRET, algorithms=["HS256"])
            email = payload.get("sub")
            if email:
                user = await db.user.find_unique(where={"email": email})
        except Exception:
            pass

    course = await db.course.find_unique(
        where={"id": course_id},
        include={"lessons": True}
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    course.lessons.sort(key=lambda l: l.orderIndex)

    # Access control: Mask video URLs and texts for unpaid/anonymous users for lessons index > 1
    processed_lessons = []
    is_premium = user is not None and user.membershipLevel == "premium"
    
    # Get user progress if logged in
    completed_lessons = set()
    if user:
        progress = await db.userprogress.find_many(where={"userId": user.id, "completed": True})
        completed_lessons = {p.lessonId for p in progress}

    for idx, lesson in enumerate(course.lessons):
        lesson_data = lesson.dict()
        lesson_data["completed"] = lesson.id in completed_lessons
        
        # Free users only get access to the first lesson (index 0)
        if idx == 0 or is_premium:
            # Full access
            pass
        else:
            # Mask sensitive data
            lesson_data["videoUrl"] = ""
            lesson_data["textContent"] = "Upgrade to premium to access this lesson's content."
            lesson_data["isLocked"] = True
            
        processed_lessons.append(lesson_data)
        
    course_data = course.dict()
    course_data["lessons"] = processed_lessons
    return course_data

@router.post("/lessons/{lesson_id}/progress")
async def update_lesson_progress(lesson_id: str, data: UserProgressRequest, current_user = Depends(get_current_user)):
    lesson = await db.lesson.find_unique(where={"id": lesson_id})
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
        
    progress = await db.userprogress.upsert(
        where={
            "userId_lessonId": {
                "userId": current_user.id,
                "lessonId": lesson_id
            }
        },
        data={
            "create": {
                "userId": current_user.id,
                "lessonId": lesson_id,
                "completed": data.completed
            },
            "update": {
                "completed": data.completed
            }
        }
    )
    return {"status": "success", "completed": progress.completed}

# ADMIN CRUD SECTION
def verify_admin(current_user = Depends(get_current_user)):
    if current_user.email != "admin@gordon.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

class CourseCreateRequest(BaseModel):
    title: str
    description: str
    thumbnailUrl: str
    difficulty: str
    isPopular: Optional[bool] = False
    courseType: Optional[str] = "STANDARD"

class CourseUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    difficulty: Optional[str] = None
    isPopular: Optional[bool] = None
    courseType: Optional[str] = None

class LessonCreateRequest(BaseModel):
    title: str
    videoUrl: str
    textContent: str
    orderIndex: int

class LessonUpdateRequest(BaseModel):
    title: Optional[str] = None
    videoUrl: Optional[str] = None
    textContent: Optional[str] = None
    orderIndex: Optional[int] = None

@router.post("", response_model=None, dependencies=[Depends(verify_admin)])
async def create_course(data: CourseCreateRequest):
    new_course = await db.course.create(
        data={
            "title": data.title,
            "description": data.description,
            "thumbnailUrl": data.thumbnailUrl,
            "difficulty": data.difficulty,
            "isPopular": data.isPopular,
            "courseType": data.courseType
        }
    )
    return new_course

@router.put("/{course_id}", response_model=None, dependencies=[Depends(verify_admin)])
async def update_course(course_id: str, data: CourseUpdateRequest):
    # Verify course exists
    course = await db.course.find_unique(where={"id": course_id})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
        
    update_data = {}
    if data.title is not None:
        update_data["title"] = data.title
    if data.description is not None:
        update_data["description"] = data.description
    if data.thumbnailUrl is not None:
        update_data["thumbnailUrl"] = data.thumbnailUrl
    if data.difficulty is not None:
        update_data["difficulty"] = data.difficulty
    if data.isPopular is not None:
        update_data["isPopular"] = data.isPopular
    if data.courseType is not None:
        update_data["courseType"] = data.courseType

    updated = await db.course.update(
        where={"id": course_id},
        data=update_data
    )
    return updated

@router.delete("/{course_id}", response_model=None, dependencies=[Depends(verify_admin)])
async def delete_course(course_id: str):
    course = await db.course.find_unique(where={"id": course_id})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Clean up lessons and progress
    lessons = await db.lesson.find_many(where={"courseId": course_id})
    lesson_ids = [l.id for l in lessons]
    
    if lesson_ids:
        await db.userprogress.delete_many(where={"lessonId": {"in": lesson_ids}})
        await db.lesson.delete_many(where={"courseId": course_id})

    await db.course.delete(where={"id": course_id})
    return {"status": "success", "message": "Course and all related lessons deleted successfully"}

@router.post("/{course_id}/lessons", response_model=None, dependencies=[Depends(verify_admin)])
async def create_lesson(course_id: str, data: LessonCreateRequest):
    course = await db.course.find_unique(where={"id": course_id})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    new_lesson = await db.lesson.create(
        data={
            "courseId": course_id,
            "title": data.title,
            "videoUrl": data.videoUrl,
            "textContent": data.textContent,
            "orderIndex": data.orderIndex
        }
    )
    return new_lesson

@router.put("/lessons/{lesson_id}", response_model=None, dependencies=[Depends(verify_admin)])
async def update_lesson(lesson_id: str, data: LessonUpdateRequest):
    lesson = await db.lesson.find_unique(where={"id": lesson_id})
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    update_data = {}
    if data.title is not None:
        update_data["title"] = data.title
    if data.videoUrl is not None:
        update_data["videoUrl"] = data.videoUrl
    if data.textContent is not None:
        update_data["textContent"] = data.textContent
    if data.orderIndex is not None:
        update_data["orderIndex"] = data.orderIndex

    updated = await db.lesson.update(
        where={"id": lesson_id},
        data=update_data
    )
    return updated

@router.delete("/lessons/{lesson_id}", response_model=None, dependencies=[Depends(verify_admin)])
async def delete_lesson(lesson_id: str):
    lesson = await db.lesson.find_unique(where={"id": lesson_id})
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    # Clean up progress first
    await db.userprogress.delete_many(where={"lessonId": lesson_id})
    await db.lesson.delete(where={"id": lesson_id})
    return {"status": "success", "message": "Lesson deleted successfully"}

