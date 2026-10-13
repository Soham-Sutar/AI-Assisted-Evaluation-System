"""Reviewer workflow service: assign, resolve, escalate.
Reviewer score (not AI) overrides faculty score for the answer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.review_case import ReviewCase, ReviewStatus
from app.models.evaluation import Evaluation
from app.models.user import User, UserRole
from app.models.answer import Answer
from app.services.audit_service import log_action
from app.services.scoring import calculate_student_score


class ReviewError(Exception):
    pass


class ReviewNotFoundError(ReviewError):
    pass


class ReviewConflictError(ReviewError):
    pass


class ReviewValidationError(ReviewError):
    pass


def _case(db: Session, case_id: str) -> ReviewCase:
    c = db.get(ReviewCase, case_id)
    if c is None:
        raise ReviewNotFoundError(f"Review case with ID '{case_id}' not found")
    return c


def check_conflict_of_interest(db: Session, case: ReviewCase, user: User) -> bool:
    """A reviewer must not re-evaluate an answer they evaluated themselves as faculty."""
    conflict_eval = db.scalar(
        select(Evaluation.id)
        .where(
            Evaluation.answer_id == case.answer_id,
            Evaluation.faculty_id == user.id,
        )
        .limit(1)
    )
    return conflict_eval is not None


def assign_reviewer(
    db: Session,
    case_id: str,
    reviewer_id: str,
    actor: User,
) -> ReviewCase:
    """Assign a review case to an eligible reviewer (or claim it)."""
    case = _case(db, case_id)
    reviewer = db.get(User, reviewer_id)
    if reviewer is None or not reviewer.is_active or reviewer.role not in (UserRole.REVIEWER, UserRole.ADMIN):
        raise ReviewConflictError("Target user cannot act as a reviewer")

    if case.status == ReviewStatus.RESOLVED:
        raise ReviewConflictError("Review case is already resolved and cannot be reassigned")

    if case.status == ReviewStatus.ASSIGNED and case.reviewer_id and case.reviewer_id != reviewer.id and actor.role != UserRole.ADMIN:
        raise ReviewConflictError("Review case is already assigned to another reviewer")

    if check_conflict_of_interest(db, case, reviewer):
        raise ReviewConflictError("Reviewer evaluated this answer and cannot review it due to conflict of interest")

    case.reviewer_id = reviewer.id
    case.status = ReviewStatus.ASSIGNED
    log_action(
        db,
        actor.id,
        "review.assigned",
        "ReviewCase",
        case.id,
        {"reviewer_id": str(reviewer.id), "assigned_by": str(actor.id)},
    )
    db.commit()
    db.refresh(case)
    return case


def resolve_case(
    db: Session,
    case_id: str,
    marks: float,
    comments: str,
    actor: User,
) -> ReviewCase:
    """Resolve a review case with reviewer-awarded marks and required comments."""
    case = _case(db, case_id)
    if case.status == ReviewStatus.RESOLVED:
        raise ReviewConflictError("Review case is already resolved")

    if case.reviewer_id not in (None, actor.id) and actor.role != UserRole.ADMIN:
        raise ReviewConflictError("Case is assigned to another reviewer")

    if check_conflict_of_interest(db, case, actor):
        raise ReviewConflictError("You evaluated this answer and cannot review it due to conflict of interest")

    question = case.answer.question if case.answer else None
    max_marks = question.max_marks if question else 10.0

    if marks < 0.0 or marks > max_marks:
        raise ReviewValidationError(f"Reviewer marks must be between 0.0 and {max_marks}")

    if not (comments or "").strip():
        raise ReviewValidationError("Reviewer comments are required to resolve a review case")

    case.reviewer_id = case.reviewer_id or actor.id
    case.reviewer_marks = marks
    case.reviewer_comments = comments.strip()
    case.status = ReviewStatus.RESOLVED
    case.resolved_at = datetime.now(timezone.utc)

    # Persist answer-level final score
    if case.answer:
        case.answer.final_marks = marks
        case.answer.final_marks_source = "REVIEWER"

    log_action(
        db,
        actor.id,
        "review.resolved",
        "ReviewCase",
        case.id,
        {"marks": marks, "answer_id": str(case.answer_id)},
    )
    db.commit()
    db.refresh(case)

    # Recalculate student final score
    if case.answer and case.answer.answer_sheet:
        sheet = case.answer.answer_sheet
        calculate_student_score(
            db,
            examination_id=sheet.examination_id,
            student_id=sheet.student_id,
            auto_commit=True,
        )

    return case


def escalate_case(
    db: Session,
    case_id: str,
    comments: Optional[str],
    actor: User,
) -> ReviewCase:
    """Escalate a review case for administrative / senior review."""
    case = _case(db, case_id)
    if case.status == ReviewStatus.RESOLVED:
        raise ReviewConflictError("Review case is already resolved and cannot be escalated")

    if case.reviewer_id not in (None, actor.id) and actor.role != UserRole.ADMIN:
        raise ReviewConflictError("Case is assigned to another reviewer")

    case.status = ReviewStatus.ESCALATED
    if (comments or "").strip():
        case.reviewer_comments = comments.strip()
    case.reviewer_id = case.reviewer_id or actor.id

    log_action(
        db,
        actor.id,
        "review.escalated",
        "ReviewCase",
        case.id,
        {"comments": comments},
    )
    db.commit()
    db.refresh(case)
    return case
