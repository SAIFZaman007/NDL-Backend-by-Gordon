from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form
from typing import List, Optional
from app.db import db
from app.routers.auth_router import get_current_user
from app.services import cloudinary_service
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


# ── Upload configuration (course thumbnails) ────────────────────
# Thumbnails are uploaded straight to Cloudinary (see
# app/services/cloudinary_service.py) — only the resulting secure_url is
# ever written to Course.thumbnailUrl, a plain, required String column, so
# prisma/schema.prisma needs no changes. save_thumbnail_image/
# delete_thumbnail_image keep their original names and signatures below;
# only their internals changed, so create_course/update_course/
# delete_course needed no further changes beyond awaiting them.
#
# The Form/File parameter on the endpoints below is deliberately still
# named "thumbnailUrl" (an UploadFile, not a string) to keep the exact
# parameter name the dashboard and this router have always used.
async def save_thumbnail_image(thumbnailUrl: UploadFile) -> str:
    """
    Validate an uploaded course thumbnail and upload it to Cloudinary.
    Returns the secure_url stored in Course.thumbnailUrl.
    """
    return await cloudinary_service.upload_image(thumbnailUrl, folder=cloudinary_service.COURSE_FOLDER)


async def delete_thumbnail_image(thumbnail_url: Optional[str]) -> None:
    """
    Best-effort removal of a Cloudinary-hosted course thumbnail. External
    URLs (e.g. seeded Unsplash images, or legacy local "/uploads/..."
    paths) are ignored silently — updating/deleting a course must never
    fail because of remote storage state.
    """
    await cloudinary_service.delete_image(thumbnail_url)


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
async def create_course(
    title: str = Form(...),
    description: str = Form(...),
    difficulty: str = Form(...),
    isPopular: Optional[bool] = Form(False),
    courseType: Optional[str] = Form("STANDARD"),
    thumbnailUrl: UploadFile = File(...),
):
    """Admin: Create a new course (multipart/form-data — thumbnailUrl is an uploaded image file, stored on Cloudinary)"""
    thumbnail_path = await save_thumbnail_image(thumbnailUrl)

    new_course = await db.course.create(
        data={
            "title": title,
            "description": description,
            "thumbnailUrl": thumbnail_path,
            "difficulty": difficulty,
            "isPopular": isPopular,
            "courseType": courseType
        }
    )
    return new_course

@router.put("/{course_id}", response_model=None, dependencies=[Depends(verify_admin)])
async def update_course(
    course_id: str,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    difficulty: Optional[str] = Form(None),
    isPopular: Optional[bool] = Form(None),
    courseType: Optional[str] = Form(None),
    thumbnailUrl: Optional[UploadFile] = File(None),
):
    """Admin: Update a course (multipart/form-data — send thumbnailUrl only to replace the current image)"""
    # Verify course exists
    course = await db.course.find_unique(where={"id": course_id})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
        
    update_data = {}
    if title is not None:
        update_data["title"] = title
    if description is not None:
        update_data["description"] = description
    if difficulty is not None:
        update_data["difficulty"] = difficulty
    if isPopular is not None:
        update_data["isPopular"] = isPopular
    if courseType is not None:
        update_data["courseType"] = courseType

    # Only replace the stored image when an actual file was uploaded.
    # Omitting thumbnailUrl keeps the existing image untouched.
    if thumbnailUrl is not None and thumbnailUrl.filename:
        new_thumbnail_path = await save_thumbnail_image(thumbnailUrl)
        await delete_thumbnail_image(course.thumbnailUrl)  # reclaim the old Cloudinary asset
        update_data["thumbnailUrl"] = new_thumbnail_path

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
    await delete_thumbnail_image(course.thumbnailUrl)  # remove the orphaned Cloudinary asset
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
