from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from app.db import db
from app.routers.auth_router import get_current_user
from pydantic import BaseModel
import datetime

router = APIRouter()

def verify_admin(current_user = Depends(get_current_user)):
    if current_user.email != "admin@gordon.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

class CourseEnrollmentStat(BaseModel):
    id: str
    title: str
    enrollment_count: int

class StatsResponse(BaseModel):
    total_users: int
    total_courses: int
    total_lessons: int
    total_questions: int
    total_revenue: float
    enrollments: List[CourseEnrollmentStat]
    revenue_growth: dict # month -> revenue
    user_growth: dict # month -> cumulative users

class UserProgressStat(BaseModel):
    id: str
    email: str
    membership_level: str
    created_at: datetime.datetime
    completed_lessons_count: int
    exam_attempts_count: int
    total_spent: float

@router.get("/stats", response_model=StatsResponse, dependencies=[Depends(verify_admin)])
async def get_admin_stats():
    # Counts
    total_users = await db.user.count()
    total_courses = await db.course.count()
    total_lessons = await db.lesson.count()
    total_questions = await db.question.count()
    
    # Total revenue
    payments = await db.payment.find_many(order={"createdAt": "asc"})
    total_revenue = sum([p.amount for p in payments])
    
    # Course enrollments (users who completed/started at least one lesson in course)
    courses = await db.course.find_many(include={"lessons": True})
    enrollments = []
    for course in courses:
        lesson_ids = [l.id for l in course.lessons]
        if lesson_ids:
            progress_users = await db.userprogress.find_many(where={"lessonId": {"in": lesson_ids}})
            distinct_users = len(set([p.userId for p in progress_users]))
        else:
            distinct_users = 0
            
        enrollments.append(CourseEnrollmentStat(
            id=course.id,
            title=course.title,
            enrollment_count=distinct_users
        ))
        
    # Group payments by month
    revenue_growth = {}
    for p in payments:
        month_str = p.createdAt.strftime("%b %Y")
        revenue_growth[month_str] = round(revenue_growth.get(month_str, 0) + p.amount, 2)
        
    # Group user signups by month (cumulative growth)
    users = await db.user.find_many(order={"createdAt": "asc"})
    user_growth_raw = {}
    for u in users:
        month_str = u.createdAt.strftime("%b %Y")
        user_growth_raw[month_str] = user_growth_raw.get(month_str, 0) + 1
        
    # Sort months by datetime parsing to prevent string sorting mismatches
    # But since users is sorted by createdAt asc, sorting keys by appearance matches timeline
    user_growth = {}
    running_users = 0
    for m in user_growth_raw.keys():
        running_users += user_growth_raw[m]
        user_growth[m] = running_users
        
    return StatsResponse(
        total_users=total_users,
        total_courses=total_courses,
        total_lessons=total_lessons,
        total_questions=total_questions,
        total_revenue=round(total_revenue, 2),
        enrollments=enrollments,
        revenue_growth=revenue_growth,
        user_growth=user_growth
    )

@router.get("/users", response_model=List[UserProgressStat], dependencies=[Depends(verify_admin)])
async def get_admin_users():
    users = await db.user.find_many(
        include={"progress": True, "attempts": True, "payments": True},
        order={"createdAt": "desc"}
    )
    
    user_stats = []
    for user in users:
        completed_lessons = len([p for p in user.progress if p.completed])
        exam_attempts = len(user.attempts)
        total_spent = sum([p.amount for p in user.payments])
        
        user_stats.append(UserProgressStat(
            id=user.id,
            email=user.email,
            membership_level=user.membershipLevel,
            created_at=user.createdAt,
            completed_lessons_count=completed_lessons,
            exam_attempts_count=exam_attempts,
            total_spent=round(total_spent, 2)
        ))
        
    return user_stats
