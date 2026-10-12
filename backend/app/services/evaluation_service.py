"""Faculty evaluation: draft/submit with strict ownership checks (IDOR protection) and marks validation."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Answer, AssignStatus, Evaluation, FacultyAssignment, Question
from app.services.assignment_service import sync_workload
from app.services.audit_service import log_action


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


def validate_marks(marks: float | None, max_marks: float, required: bool = False) -> float | None:
    """0 <= marks <= max_marks. Raises ValueError otherwise."""
    if marks is None:
        if required:
            raise ValueError("Marks are required to submit an evaluation")
        return None
    if marks != marks:  # NaN
        raise ValueError("Marks must be a number")
    if marks < 0 or marks > max_marks:
        raise ValueError(f"Marks must be between 0 and {max_marks:g}")
    return float(marks)


def get_owned_assignment(db: Session, answer_id: uuid.UUID, faculty_id: uuid.UUID) -> FacultyAssignment:
    """Returns the faculty's assignment for this answer or raises NotFound (404, not 403: no enumeration)."""
    a = db.scalar(select(FacultyAssignment).where(
        FacultyAssignment.answer_id == answer_id, FacultyAssignment.faculty_id == faculty_id,
        FacultyAssignment.status.in_((*AssignStatus.ACTIVE, AssignStatus.COMPLETED)))
        .order_by(FacultyAssignment.assigned_at.desc()).limit(1))
    if a is None:
        raise NotFound("Answer not found")
    return a


def _current_eval(db: Session, answer_id, faculty_id) -> Evaluation | None:
    return db.scalar(select(Evaluation).where(Evaluation.answer_id == answer_id, Evaluation.faculty_id == faculty_id)
                     .order_by(Evaluation.version.desc()).limit(1))


def save_evaluation(db: Session, answer_id: uuid.UUID, faculty_id: uuid.UUID, marks: float | None, comments: str | None,
                    submit: bool) -> Evaluation:
    assignment = get_owned_assignment(db, answer_id, faculty_id)
    answer = db.get(Answer, answer_id)
    q: Question = answer.question
    marks = validate_marks(marks, q.max_marks, required=submit)
    ev = _current_eval(db, answer_id, faculty_id)
    if ev is not None and not ev.is_draft:
        raise Conflict("This evaluation has already been submitted and is locked")
    if assignment.status == AssignStatus.COMPLETED and ev is None:
        raise Conflict("Assignment already completed")
    if ev is None:
        ev = Evaluation(answer_id=answer_id, faculty_id=faculty_id, assignment_id=assignment.id, max_marks=q.max_marks,
                        version=1)
        db.add(ev)
    ev.marks_awarded, ev.comments = marks, (comments or None)
    now = datetime.now(timezone.utc)
    if assignment.started_at is None:
        assignment.started_at = now
    if submit:
        ev.is_draft, ev.submitted_at = False, now
        assignment.status, assignment.completed_at = AssignStatus.COMPLETED, now
        db.flush()
        sync_workload(db, faculty_id)
        log_action(db, faculty_id, "evaluation.submitted", "Answer", answer_id,
                   {"marks": marks, "max_marks": q.max_marks, "version": ev.version})
    else:
        assignment.status = AssignStatus.IN_PROGRESS
        log_action(db, faculty_id, "evaluation.draft_saved", "Answer", answer_id, {"marks": marks})
    db.commit()
    return ev


def correct_ocr(db: Session, answer_id: uuid.UUID, text: str, user) -> Answer:
    """Faculty may correct OCR only for their own, not-yet-submitted assignment; admin always.
    The machine OCR is preserved in original_ocr_text."""
    from app.models import Role
    answer = db.get(Answer, answer_id)
    if answer is None:
        raise NotFound("Answer not found")
    if user.role == Role.FACULTY:
        a = get_owned_assignment(db, answer_id, user.id)
        if a.status == AssignStatus.COMPLETED:
            raise Conflict("Evaluation already submitted; OCR text is locked")
    if answer.original_ocr_text is None:
        answer.original_ocr_text = answer.extracted_text
    answer.extracted_text = text
    answer.ocr_corrected = True
    answer.ocr_status = "OK"
    log_action(db, user.id, "ocr.corrected", "Answer", answer_id, {"chars": len(text)})
    db.commit()
    return answer
