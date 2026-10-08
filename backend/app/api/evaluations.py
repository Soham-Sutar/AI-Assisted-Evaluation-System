import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.core.database import get_db
from app.api.deps import get_current_active_user, require_roles
from app.models.user import User, UserRole
from app.models.assignment import Assignment, AssignmentStatus
from app.models.evaluation import Evaluation
from app.schemas.evaluation import EvaluationCreate, EvaluationRead

logger = logging.getLogger("evalai.api.evaluations")

router = APIRouter(prefix="/evaluations", tags=["Evaluations"])


def _enrich_evaluation(evaluation: Evaluation) -> EvaluationRead:
    faculty = evaluation.faculty
    answer = evaluation.answer
    question = answer.question if answer else None
    examination = question.examination if question else None

    return EvaluationRead(
        id=evaluation.id,
        answer_id=evaluation.answer_id,
        faculty_id=evaluation.faculty_id,
        assignment_id=evaluation.assignment_id,
        marks_awarded=evaluation.marks_awarded,
        max_marks=evaluation.max_marks,
        comments=evaluation.comments,
        submitted_at=evaluation.submitted_at,
        version=evaluation.version,
        faculty_name=faculty.full_name if faculty else None,
        question_number=question.question_number if question else None,
        examination_name=examination.name if examination else None,
    )


@router.post("/", response_model=EvaluationRead, status_code=status.HTTP_201_CREATED)
def submit_evaluation(
    payload: EvaluationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
):
    """Faculty: Submit human evaluation for an assigned answer."""
    # Retrieve the assignment
    assignment = db.scalars(select(Assignment).where(Assignment.id == payload.assignment_id)).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment with ID '{payload.assignment_id}' not found",
        )

    # Prevent IDOR: Faculty can only evaluate their own assignments
    if assignment.faculty_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to evaluate this assignment",
        )

    # Check assignment status
    if assignment.status not in [AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit evaluation for assignment in status '{assignment.status.value}'",
        )

    # Check if evaluation already exists
    existing_evaluation = db.scalars(
        select(Evaluation).where(Evaluation.assignment_id == assignment.id)
    ).first()
    if existing_evaluation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evaluation already submitted for this assignment",
        )

    answer = assignment.answer
    question = answer.question
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Associated answer has no mapped question. Cannot determine maximum marks.",
        )

    max_marks = question.max_marks

    # Validate marks
    if payload.marks_awarded < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Marks awarded cannot be negative",
        )
    if payload.marks_awarded > max_marks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Marks awarded ({payload.marks_awarded}) exceed maximum marks for the question ({max_marks})",
        )

    # Create Evaluation
    evaluation = Evaluation(
        answer_id=answer.id,
        faculty_id=current_user.id,
        assignment_id=assignment.id,
        marks_awarded=payload.marks_awarded,
        max_marks=max_marks,
        comments=payload.comments,
    )
    
    # Update Assignment Status to COMPLETED
    assignment.status = AssignmentStatus.COMPLETED

    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    
    logger.info(
        "Evaluation submitted: %s (faculty=%s assignment=%s marks=%s/%s)",
        evaluation.id,
        current_user.id,
        assignment.id,
        evaluation.marks_awarded,
        max_marks,
    )

    return _enrich_evaluation(evaluation)


@router.get("/me/list", response_model=List[EvaluationRead])
def list_my_evaluations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
):
    """Faculty: List all submitted evaluations by the current faculty member."""
    evaluations = db.scalars(
        select(Evaluation).where(Evaluation.faculty_id == current_user.id).order_by(Evaluation.submitted_at.desc())
    ).all()
    
    return [_enrich_evaluation(e) for e in evaluations]


@router.get("/me/{evaluation_id}", response_model=EvaluationRead)
def get_my_evaluation(
    evaluation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
):
    """Faculty: Retrieve a specific evaluation submitted by the current faculty member."""
    evaluation = db.scalars(
        select(Evaluation).where(
            and_(
                Evaluation.id == evaluation_id,
                Evaluation.faculty_id == current_user.id,
            )
        )
    ).first()
    
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation with ID '{evaluation_id}' not found",
        )
        
    return _enrich_evaluation(evaluation)
