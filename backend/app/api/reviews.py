import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_active_user, require_roles
from app.models.user import User, UserRole
from app.models.answer import Answer
from app.models.assignment import Assignment
from app.models.evaluation import Evaluation
from app.models.ai_evaluation import AIEvaluation, AIEvaluationStatus
from app.models.review_case import (
    ReviewCase,
    ReviewTriggerType,
    ReviewStatus,
    ReviewPriority,
)
from app.schemas.review_case import ReviewCaseRead, DiscrepancyCheckResponse
from app.services.discrepancy import (
    compute_discrepancy,
    detect_and_create_review_case,
    enrich_review_case,
)


logger = logging.getLogger("evalai.api.reviews")

router = APIRouter(tags=["Reviews & Discrepancies"])


def _check_faculty_can_access_answer_discrepancy(
    db: Session, faculty_user: User, answer: Answer
) -> None:
    """
    Enforces evaluation independence and resource ownership (prevent IDOR & anti-anchoring):
    1. Faculty must be assigned to this answer.
    2. Faculty must have already submitted their human evaluation before discrepancy/AI score can be accessed.
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
            detail="Discrepancy and AI evaluation details are hidden until human faculty evaluation has been submitted",
        )


def _build_discrepancy_response(
    answer_id: str, metrics, review_case: Optional[ReviewCase]
) -> DiscrepancyCheckResponse:
    if metrics.is_discrepant:
        message = (
            f"Significant score discrepancy detected: faculty score {metrics.faculty_marks} "
            f"vs AI reference score {metrics.ai_marks} (diff {metrics.difference}/{metrics.max_marks}). "
            "Review case active."
        )
    else:
        message = (
            f"Scores are consistent: faculty score {metrics.faculty_marks} "
            f"vs AI reference score {metrics.ai_marks} (diff {metrics.difference}/{metrics.max_marks}). "
            "No review needed."
        )

    return DiscrepancyCheckResponse(
        answer_id=answer_id,
        faculty_marks=metrics.faculty_marks,
        ai_marks=metrics.ai_marks,
        max_marks=metrics.max_marks,
        absolute_difference=metrics.difference,
        relative_difference=metrics.normalized_difference,
        absolute_threshold=metrics.absolute_threshold,
        relative_threshold=metrics.relative_threshold,
        is_discrepant=metrics.is_discrepant,
        discrepancy_detected=metrics.is_discrepant,
        has_discrepancy=metrics.is_discrepant,
        discrepancy_amount=metrics.difference,
        review_case=enrich_review_case(review_case) if review_case else None,
        message=message,
    )


# --- Discrepancy Detection Endpoints ---

@router.post(
    "/answers/{answer_id}/discrepancy",
    response_model=DiscrepancyCheckResponse,
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/answers/{answer_id}/detect-discrepancy",
    response_model=DiscrepancyCheckResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@router.post(
    "/answers/{answer_id}/discrepancy-check",
    response_model=DiscrepancyCheckResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def run_discrepancy_check(
    answer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Run discrepancy detection for an answer.
    Compares faculty evaluation against independent AI evaluation.
    If discrepancy thresholds are exceeded, creates a ReviewCase.
    """
    answer = db.get(Answer, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer with ID '{answer_id}' not found",
        )

    if current_user.role == UserRole.FACULTY:
        _check_faculty_can_access_answer_discrepancy(db, current_user, answer)
    elif current_user.role not in [UserRole.ADMIN, UserRole.REVIEWER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to run discrepancy detection",
        )

    metrics, review_case = detect_and_create_review_case(db, answer_id)
    return _build_discrepancy_response(answer_id, metrics, review_case)


@router.get(
    "/answers/{answer_id}/discrepancy",
    response_model=DiscrepancyCheckResponse,
)
def get_answer_discrepancy(
    answer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve current discrepancy analysis and associated review case (if any) for an answer.
    """
    answer = db.get(Answer, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer with ID '{answer_id}' not found",
        )

    if current_user.role == UserRole.FACULTY:
        _check_faculty_can_access_answer_discrepancy(db, current_user, answer)
    elif current_user.role not in [UserRole.ADMIN, UserRole.REVIEWER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view discrepancy details",
        )

    faculty_eval = db.scalars(
        select(Evaluation).where(Evaluation.answer_id == answer_id)
    ).first()
    if not faculty_eval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submitted faculty evaluation is required to evaluate discrepancy",
        )

    ai_eval = db.scalars(
        select(AIEvaluation).where(AIEvaluation.answer_id == answer_id)
    ).first()
    if not ai_eval or ai_eval.status != AIEvaluationStatus.COMPLETED or ai_eval.ai_marks is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completed AI evaluation is required to evaluate discrepancy",
        )

    max_marks = float(ai_eval.max_marks or faculty_eval.max_marks or (answer.question.max_marks if answer.question else 10.0))
    metrics = compute_discrepancy(
        faculty_marks=faculty_eval.marks_awarded,
        ai_marks=ai_eval.ai_marks,
        max_marks=max_marks,
        abs_threshold=settings.DISCREPANCY_ABSOLUTE_THRESHOLD,
        rel_threshold=settings.DISCREPANCY_RELATIVE_THRESHOLD,
    )


    existing_case = db.scalars(
        select(ReviewCase)
        .where(
            ReviewCase.answer_id == answer_id,
            ReviewCase.trigger_type == ReviewTriggerType.AI_HUMAN_DISCREPANCY,
        )
        .order_by(ReviewCase.created_at.desc())
    ).first()

    return _build_discrepancy_response(answer_id, metrics, existing_case)



# --- Review Case Endpoints ---

@router.get("/reviews", response_model=List[ReviewCaseRead])
def list_review_cases(
    status: Optional[ReviewStatus] = None,
    trigger_type: Optional[ReviewTriggerType] = None,
    priority: Optional[ReviewPriority] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
):
    """
    List review cases with pagination and optional filters.
    Restricted to ADMIN and REVIEWER roles.
    """
    stmt = select(ReviewCase)
    if status is not None:
        stmt = stmt.where(ReviewCase.status == status)
    if trigger_type is not None:
        stmt = stmt.where(ReviewCase.trigger_type == trigger_type)
    if priority is not None:
        stmt = stmt.where(ReviewCase.priority == priority)

    stmt = stmt.order_by(ReviewCase.created_at.desc()).offset(skip).limit(limit)
    cases = db.scalars(stmt).all()
    return [enrich_review_case(c) for c in cases]


@router.get("/reviews/{review_id}", response_model=ReviewCaseRead)
def get_review_case(
    review_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve details of a single review case by ID.
    - ADMIN and REVIEWER can access all review cases.
    - FACULTY can only access if assigned to the underlying answer AND has already evaluated it.
    """
    case = db.get(ReviewCase, review_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review case with ID '{review_id}' not found",
        )

    if current_user.role == UserRole.FACULTY:
        _check_faculty_can_access_answer_discrepancy(db, current_user, case.answer)
    elif current_user.role not in [UserRole.ADMIN, UserRole.REVIEWER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access this review case",
        )

    return enrich_review_case(case)
