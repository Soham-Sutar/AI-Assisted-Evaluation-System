"""Reviewer workflow: assign / resolve / escalate. Reviewer score (not AI) overrides faculty score for the answer."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Evaluation, ReviewCase, ReviewStatus, Role, User
from app.services.audit_service import log_action
from app.services.evaluation_service import Conflict, NotFound, validate_marks
from app.services.result_service import recalc_for_answer


def _case(db: Session, case_id) -> ReviewCase:
    c = db.get(ReviewCase, case_id)
    if c is None:
        raise NotFound("Review case not found")
    return c


def _conflict_of_interest(db: Session, case: ReviewCase, user: User) -> bool:
    """A reviewer must not re-evaluate an answer they scored themselves (reviewers may also be faculty)."""
    return db.scalar(select(Evaluation.id).where(Evaluation.answer_id == case.answer_id,
                                                 Evaluation.faculty_id == user.id).limit(1)) is not None


def assign_reviewer(db: Session, case_id, reviewer_id, actor: User) -> ReviewCase:
    case = _case(db, case_id)
    reviewer = db.get(User, reviewer_id)
    if reviewer is None or not reviewer.is_active or reviewer.role not in (Role.REVIEWER, Role.ADMIN):
        raise Conflict("Target user cannot act as a reviewer")
    if case.status == ReviewStatus.RESOLVED:
        raise Conflict("Review case is already resolved")
    if _conflict_of_interest(db, case, reviewer):
        raise Conflict("Reviewer evaluated this answer and cannot review it")
    case.reviewer_id, case.status = reviewer.id, ReviewStatus.ASSIGNED
    log_action(db, actor.id, "review.assigned", "ReviewCase", case.id, {"reviewer": str(reviewer.id)})
    db.commit()
    return case


def resolve(db: Session, case_id, marks: float, comments: str, user: User) -> ReviewCase:
    case = _case(db, case_id)
    if case.status == ReviewStatus.RESOLVED:
        raise Conflict("Review case is already resolved")
    if case.reviewer_id not in (None, user.id) and user.role != Role.ADMIN:
        raise Conflict("Case is assigned to another reviewer")
    if _conflict_of_interest(db, case, user):
        raise Conflict("You evaluated this answer and cannot review it")
    max_marks = case.answer.question.max_marks
    marks = validate_marks(marks, max_marks, required=True)
    if not (comments or "").strip():
        raise ValueError("A review comment is required")
    case.reviewer_id = case.reviewer_id or user.id
    case.reviewer_marks, case.reviewer_comments = marks, comments.strip()
    case.status, case.resolved_at = ReviewStatus.RESOLVED, datetime.now(timezone.utc)
    log_action(db, user.id, "review.resolved", "ReviewCase", case.id,
               {"marks": marks, "answer_id": str(case.answer_id)})
    db.commit()
    recalc_for_answer(db, case.answer_id, user.id)
    return case


def escalate(db: Session, case_id, comments: str, user: User) -> ReviewCase:
    case = _case(db, case_id)
    if case.status == ReviewStatus.RESOLVED:
        raise Conflict("Review case is already resolved")
    case.status = ReviewStatus.ESCALATED
    case.reviewer_comments = (comments or "").strip() or case.reviewer_comments
    case.reviewer_id = case.reviewer_id or user.id
    log_action(db, user.id, "review.escalated", "ReviewCase", case.id, {})
    db.commit()
    return case
