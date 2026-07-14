from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional
from app.db import db
from app.routers.auth_router import get_current_user

router = APIRouter()

class InterviewQuestionCreate(BaseModel):
    topic: str
    questionText: str
    correctAnswer: str

class InterviewQuestionUpdate(BaseModel):
    topic: Optional[str] = None
    questionText: Optional[str] = None
    correctAnswer: Optional[str] = None

@router.get("", response_model=List[dict])
async def get_all_interview_questions():
    questions = await db.interviewquestion.find_many(
        order={"createdAt": "desc"}
    )
    return [q.model_dump() for q in questions]

@router.get("/topic/{topic}", response_model=List[dict])
async def get_questions_by_topic(topic: str):
    questions = await db.interviewquestion.find_many(
        where={"topic": {"equals": topic, "mode": "insensitive"}},
        order={"createdAt": "asc"}
    )
    return [q.model_dump() for q in questions]

@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_interview_question(
    data: InterviewQuestionCreate,
    current_user=Depends(get_current_user)
):
    if current_user.email != "admin@gordon.com":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    question = await db.interviewquestion.create(
        data={
            "topic": data.topic,
            "questionText": data.questionText,
            "correctAnswer": data.correctAnswer
        }
    )
    return question.model_dump()

@router.put("/{question_id}", response_model=dict)
async def update_interview_question(
    question_id: str,
    data: InterviewQuestionUpdate,
    current_user=Depends(get_current_user)
):
    if current_user.email != "admin@gordon.com":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    existing = await db.interviewquestion.find_unique(where={"id": question_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Question not found")
        
    update_data = {}
    if data.topic is not None:
        update_data["topic"] = data.topic
    if data.questionText is not None:
        update_data["questionText"] = data.questionText
    if data.correctAnswer is not None:
        update_data["correctAnswer"] = data.correctAnswer
        
    updated = await db.interviewquestion.update(
        where={"id": question_id},
        data=update_data
    )
    return updated.model_dump()

@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interview_question(
    question_id: str,
    current_user=Depends(get_current_user)
):
    if current_user.email != "admin@gordon.com":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    existing = await db.interviewquestion.find_unique(where={"id": question_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Question not found")
        
    await db.interviewquestion.delete(where={"id": question_id})
    return None
