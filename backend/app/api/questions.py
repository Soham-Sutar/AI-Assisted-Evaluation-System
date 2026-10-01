from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import require_roles
from app.models.user import User, UserRole
from app.models.examination import Examination
from app.models.question import Question
from app.schemas.question import QuestionCreate, QuestionUpdate, QuestionRead

router = APIRouter(prefix="/examinations/{examination_id}/questions", tags=["Questions"])


@router.post("/", response_model=QuestionRead, status_code=status.HTTP_201_CREATED)
def create_question(
    examination_id: str,
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> QuestionRead:
    """Create a new question for an examination with optional model answer and rubric (Admin only)."""
    exam = db.get(Examination, examination_id)
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Examination with ID '{examination_id}' not found.",
        )

    # Check for duplicate question number
    stmt = select(Question).where(
        Question.examination_id == examination_id,
        Question.question_number == payload.question_number,
    )
    if db.scalars(stmt).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Question number {payload.question_number} already exists for this examination.",
        )

    question = Question(
        examination_id=examination_id,
        question_number=payload.question_number,
        question_text=payload.question_text.strip(),
        max_marks=payload.max_marks,
        model_answer_text=payload.model_answer_text.strip() if payload.model_answer_text else None,
        rubric_json=payload.rubric_json,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.get("/", response_model=List[QuestionRead])
def list_questions(
    examination_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
) -> List[QuestionRead]:
    """List all questions for an examination ordered by question number (Admin and Faculty)."""
    exam = db.get(Examination, examination_id)
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Examination with ID '{examination_id}' not found.",
        )

    stmt = (
        select(Question)
        .where(Question.examination_id == examination_id)
        .order_by(Question.question_number.asc())
    )
    return list(db.scalars(stmt).all())


@router.get("/{question_id}", response_model=QuestionRead)
def get_question(
    examination_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
) -> QuestionRead:
    """Get question details by ID (Admin and Faculty)."""
    stmt = select(Question).where(
        Question.id == question_id,
        Question.examination_id == examination_id,
    )
    question = db.scalars(stmt).first()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question with ID '{question_id}' not found for examination '{examination_id}'.",
        )
    return question


@router.put("/{question_id}", response_model=QuestionRead)
def update_question(
    examination_id: str,
    question_id: str,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> QuestionRead:
    """Update question content, marks, model answer, or rubric criteria (Admin only)."""
    stmt = select(Question).where(
        Question.id == question_id,
        Question.examination_id == examination_id,
    )
    question = db.scalars(stmt).first()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question with ID '{question_id}' not found for examination '{examination_id}'.",
        )

    if payload.question_number is not None and payload.question_number != question.question_number:
        existing = db.scalars(
            select(Question).where(
                Question.examination_id == examination_id,
                Question.question_number == payload.question_number,
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Question number {payload.question_number} already exists for this examination.",
            )
        question.question_number = payload.question_number

    if payload.question_text is not None:
        question.question_text = payload.question_text.strip()
    if payload.max_marks is not None:
        question.max_marks = payload.max_marks
    if payload.model_answer_text is not None:
        question.model_answer_text = payload.model_answer_text.strip() if payload.model_answer_text else None
    if payload.rubric_json is not None:
        question.rubric_json = payload.rubric_json

    db.commit()
    db.refresh(question)
    return question


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    examination_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Delete a question from an examination (Admin only)."""
    stmt = select(Question).where(
        Question.id == question_id,
        Question.examination_id == examination_id,
    )
    question = db.scalars(stmt).first()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question with ID '{question_id}' not found for examination '{examination_id}'.",
        )
    db.delete(question)
    db.commit()
    return None
