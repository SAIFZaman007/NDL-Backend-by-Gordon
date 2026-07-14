from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from app.db import db
from app.routers.auth_router import get_current_user
from pydantic import BaseModel

router = APIRouter()

def verify_admin(current_user = Depends(get_current_user)):
    if current_user.email != "admin@gordon.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

class LearningPathCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    pathType: str
    iconUrl: Optional[str] = None

class LearningPathUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    pathType: Optional[str] = None
    iconUrl: Optional[str] = None

class CourseOnPathRequest(BaseModel):
    courseId: str
    orderIndex: int

@router.get("")
async def get_learning_paths(pathType: Optional[str] = None):
    where_clause = {}
    if pathType:
        where_clause["pathType"] = pathType
        
    paths = await db.learningpath.find_many(
        where=where_clause if where_clause else None,
        include={
            "courses": {
                "include": {
                    "course": True
                },
                "order_by": {
                    "orderIndex": "asc"
                }
            }
        }
    )
    return paths

@router.get("/{path_id}")
async def get_learning_path(path_id: str):
    path = await db.learningpath.find_unique(
        where={"id": path_id},
        include={
            "courses": {
                "include": {
                    "course": True
                },
                "order_by": {
                    "orderIndex": "asc"
                }
            }
        }
    )
    if not path:
        raise HTTPException(status_code=404, detail="Learning Path not found")
    return path

@router.post("", dependencies=[Depends(verify_admin)])
async def create_learning_path(data: LearningPathCreateRequest):
    return await db.learningpath.create(
        data={
            "title": data.title,
            "description": data.description,
            "pathType": data.pathType,
            "iconUrl": data.iconUrl
        }
    )

@router.put("/{path_id}", dependencies=[Depends(verify_admin)])
async def update_learning_path(path_id: str, data: LearningPathUpdateRequest):
    path = await db.learningpath.find_unique(where={"id": path_id})
    if not path:
        raise HTTPException(status_code=404, detail="Learning Path not found")
        
    update_data = {}
    if data.title is not None: update_data["title"] = data.title
    if data.description is not None: update_data["description"] = data.description
    if data.pathType is not None: update_data["pathType"] = data.pathType
    if data.iconUrl is not None: update_data["iconUrl"] = data.iconUrl
        
    return await db.learningpath.update(where={"id": path_id}, data=update_data)

@router.delete("/{path_id}", dependencies=[Depends(verify_admin)])
async def delete_learning_path(path_id: str):
    path = await db.learningpath.find_unique(where={"id": path_id})
    if not path:
        raise HTTPException(status_code=404, detail="Learning Path not found")
        
    # Delete related join records first
    await db.courseonlearningpath.delete_many(where={"learningPathId": path_id})
    await db.learningpath.delete(where={"id": path_id})
    return {"status": "success"}

@router.post("/{path_id}/courses", dependencies=[Depends(verify_admin)])
async def add_course_to_path(path_id: str, data: CourseOnPathRequest):
    path = await db.learningpath.find_unique(where={"id": path_id})
    if not path:
        raise HTTPException(status_code=404, detail="Learning Path not found")
    
    course = await db.course.find_unique(where={"id": data.courseId})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
        
    return await db.courseonlearningpath.create(
        data={
            "learningPathId": path_id,
            "courseId": data.courseId,
            "orderIndex": data.orderIndex
        }
    )

@router.delete("/{path_id}/courses/{course_id}", dependencies=[Depends(verify_admin)])
async def remove_course_from_path(path_id: str, course_id: str):
    await db.courseonlearningpath.delete(
        where={
            "learningPathId_courseId": {
                "learningPathId": path_id,
                "courseId": course_id
            }
        }
    )
    return {"status": "success"}
