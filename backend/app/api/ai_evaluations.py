import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.core.database import get_db
from app.api.deps import get_current_active_user, require_roles
from app.models.user import User, UserRole
from app.models.answer import Answer
from app.models.assignment import Assignment
from app.models.evaluation import Evaluation
from app.models.ai_evaluation import AIEvaluation, AIEvaluationStatus
from app.schemas.ai_evaluation import AIEvaluationRead, AIEvaluationTrigger
from app.services.ai_evaluator import evaluate_student_answer

logger = logging.getLogger("evalai.api.ai_evaluations")

router = APIRouter(tags=["AI Evaluations"])


def _check_faculty_can_view_ai_evaluation(db: Session, faculty_user: User, answer: Answer) -> None:
    """
    Enforces evaluation independence:
    1. Faculty must be assigned to this answer (prevent IDOR).
    2. Faculty must have already submitted their human evaluation before AI score can be revealed.
    """
    assignment = db.scalars(
        select(Assignment).where(
            and_(
                Assignment.answer_id == answer.id,
                Assignment.faculty_id == faculty_user.id,
            )
        )
    ).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to evaluate this answer",
        )

    # Check if faculty has submitted their human evaluation
    human_eval = db.scalars(
        select(Evaluation).where(
            and_(
                Evaluation.answer_id == answer.id,
                Evaluation.faculty_id == faculty_user.id,
            )
        )
    ).first()
    if not human_eval:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI evaluation score is hidden until human faculty evaluation has been submitted",
        )


@router.post("/answers/{answer_id}/ai-evaluate", response_model=AIEvaluationRead, status_code=status.HTTP_200_OK)
def trigger_ai_evaluation(
    answer_id: str,
    payload: Optional[AIEvaluationTrigger] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
):
    """
    Trigger independent AI reference evaluation for an answer.
    Advisory only - never overrides or modifies faculty marks.
    Restricted to ADMIN and REVIEWER to prevent faculty anchoring.
    """
    answer = db.get(Answer, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer with ID '{answer_id}' not found",
        )

    force = payload.force_reevaluate if payload else False
    ai_eval = evaluate_student_answer(db, answer_id, force_reevaluate=force)
    return ai_eval


@router.get("/answers/{answer_id}/ai-evaluation", response_model=AIEvaluationRead)
def get_answer_ai_evaluation(
    answer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve the AI reference evaluation for a specific answer.
    - ADMIN and REVIEWER can access at any time.
    - FACULTY can only access after their own evaluation has been submitted (anti-anchoring).
    """
    answer = db.get(Answer, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer with ID '{answer_id}' not found",
        )

    if current_user.role == UserRole.FACULTY:
        _check_faculty_can_view_ai_evaluation(db, current_user, answer)
    elif current_user.role not in [UserRole.ADMIN, UserRole.REVIEWER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access AI evaluations",
        )

    if not answer.ai_evaluations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI evaluation found for answer with ID '{answer_id}'",
        )

    return answer.ai_evaluations[0]


@router.get("/ai-evaluations/{evaluation_id}", response_model=AIEvaluationRead)
def get_ai_evaluation_by_id(
    evaluation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve a specific AI evaluation record by its UUID.
    """
    ai_eval = db.get(AIEvaluation, evaluation_id)
    if not ai_eval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI evaluation with ID '{evaluation_id}' not found",
        )

    if current_user.role == UserRole.FACULTY:
        _check_faculty_can_view_ai_evaluation(db, current_user, ai_eval.answer)
    elif current_user.role not in [UserRole.ADMIN, UserRole.REVIEWER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access AI evaluations",
        )

    return ai_eval
