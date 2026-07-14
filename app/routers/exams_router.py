from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from app.db import db
from app.routers.auth_router import get_current_user
from app.routers.courses_router import verify_admin
from pydantic import BaseModel

router = APIRouter()

class ExamAttemptRequest(BaseModel):
    score: int
    passed: bool

class QuestionCreateRequest(BaseModel):
    category: str
    questionText: str
    options: List[str]
    correctOption: str
    explanation: str
    indexNumber: int

@router.get("/questions")
async def get_exam_questions(category: Optional[str] = None, user_token: Optional[str] = None):
    # Determine the user
    user = None
    if user_token:
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

    is_premium = user is not None and user.membershipLevel == "premium"

    # Base query
    query_args = {}
    if category:
        query_args["category"] = category

    # Fetch questions
    questions = await db.question.find_many(
        where=query_args,
        order={"indexNumber": "asc"}
    )

    # Apply paywall: Only return indexNumber <= 40 for free/anonymous users
    allowed_questions = []
    for q in questions:
        if q.indexNumber <= 40 or is_premium:
            allowed_questions.append(q)
        else:
            # We can either stop adding or append locked questions.
            # Let's append questions but mask their content (e.g. choices, answer, explanation)
            # so the frontend knows they exist but are locked, which encourages subscription!
            locked_q = q.dict()
            locked_q["questionText"] = "Upgrade to premium to unlock this practice question."
            locked_q["options"] = []
            locked_q["correctOption"] = ""
            locked_q["explanation"] = ""
            locked_q["isLocked"] = True
            allowed_questions.append(locked_q)

    return allowed_questions

@router.post("/attempts")
async def save_exam_attempt(data: ExamAttemptRequest, current_user = Depends(get_current_user)):
    attempt = await db.userexamattempt.create(
        data={
            "userId": current_user.id,
            "score": data.score,
            "passed": data.passed
        }
    )
    return attempt

@router.get("/attempts")
async def get_exam_attempts(current_user = Depends(get_current_user)):
    attempts = await db.userexamattempt.find_many(
        where={"userId": current_user.id},
        order={"completedAt": "desc"}
    )
    return attempts

@router.post("/questions", response_model=None, dependencies=[Depends(verify_admin)])
async def create_exam_question(data: QuestionCreateRequest):
    existing = await db.question.find_unique(where={"indexNumber": data.indexNumber})
    if existing:
        raise HTTPException(status_code=400, detail="Question with this index number already exists")

    # The single most important integrity rule for this whole feature: the
    # correct answer must be one of the actual options, verbatim. If this
    # ever drifts (a typo, a rephrase, a client that skips the dashboard's
    # own guard), every attempt against this question silently scores wrong
    # forever, no matter what a student picks. Enforcing it here — the one
    # path every question write goes through — makes that class of bug
    # impossible regardless of which client is calling this endpoint.
    if data.correctOption not in data.options:
        raise HTTPException(
            status_code=400,
            detail="correctOption must exactly match one of the provided options."
        )

    from app.prisma_client import Json
    new_q = await db.question.create(
        data={
            "category": data.category,
            "questionText": data.questionText,
            "options": Json(data.options),
            "correctOption": data.correctOption,
            "explanation": data.explanation,
            "indexNumber": data.indexNumber
        }
    )
    return new_q

class QuestionUpdateRequest(BaseModel):
    category: Optional[str] = None
    questionText: Optional[str] = None
    options: Optional[List[str]] = None
    correctOption: Optional[str] = None
    explanation: Optional[str] = None
    indexNumber: Optional[int] = None

@router.put("/questions/{question_id}", response_model=None, dependencies=[Depends(verify_admin)])
async def update_exam_question(question_id: str, data: QuestionUpdateRequest):
    existing = await db.question.find_unique(where={"id": question_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Question not found")

    if data.indexNumber is not None and data.indexNumber != existing.indexNumber:
        check_index = await db.question.find_unique(where={"indexNumber": data.indexNumber})
        if check_index:
            raise HTTPException(status_code=400, detail="Question with this index number already exists")

    # Same integrity rule as create — resolve against whichever options are
    # in effect after this update (newly submitted ones if provided, the
    # question's existing ones otherwise) so a partial update can never
    # leave correctOption pointing at an option that isn't actually there.
    effective_options = data.options if data.options is not None else existing.options
    effective_correct = data.correctOption if data.correctOption is not None else existing.correctOption
    if effective_correct not in (effective_options or []):
        raise HTTPException(
            status_code=400,
            detail="correctOption must exactly match one of the question's options."
        )

    update_data = {}
    if data.category is not None:
        update_data["category"] = data.category
    if data.questionText is not None:
        update_data["questionText"] = data.questionText
    if data.options is not None:
        from app.prisma_client import Json
        update_data["options"] = Json(data.options)
    if data.correctOption is not None:
        update_data["correctOption"] = data.correctOption
    if data.explanation is not None:
        update_data["explanation"] = data.explanation
    if data.indexNumber is not None:
        update_data["indexNumber"] = data.indexNumber

    updated = await db.question.update(
        where={"id": question_id},
        data=update_data
    )
    return updated

@router.delete("/questions/{question_id}", response_model=None, dependencies=[Depends(verify_admin)])
async def delete_exam_question(question_id: str):
    existing = await db.question.find_unique(where={"id": question_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Question not found")

    await db.question.delete(where={"id": question_id})
    return {"status": "success", "message": "Question deleted successfully"}