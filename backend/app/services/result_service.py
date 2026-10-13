"""Final-score aggregation and result services.
Per answer: resolved review -> reviewer marks; otherwise submitted faculty marks. AI never contributes.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.answer import Answer
from app.models.answer_sheet import AnswerSheet
from app.models.evaluation import Evaluation
from app.models.examination import Examination, ExamStatus
from app.models.final_score import FinalScore, FinalScoreStatus
from app.models.question import Question
from app.models.review_case import ReviewCase, ReviewStatus
from app.models.student import Student
from app.services.audit_service import log_action
from app.services.scoring import (
    calculate_student_score,
    calculate_examination_scores,
    get_student_result_response,
    get_examination_results_response,
    export_examination_results_csv,
)

logger = logging.getLogger("evalai.result_service")

OPEN_STATES = [ReviewStatus.OPEN, ReviewStatus.ASSIGNED, ReviewStatus.ESCALATED]


def aggregate(per_question: list[dict], maximum: float) -> tuple[float, float, str]:
    """Pure aggregation function.
    per_question items: {marks: float|None, review_pending: bool}.
    Returns (total, percentage, status).
    """
    total = round(sum(q["marks"] for q in per_question if q.get("marks") is not None), 2)
    pct = round(total / maximum * 100, 2) if maximum > 0 else 0.0
    if any(q.get("marks") is None for q in per_question):
        status = FinalScoreStatus.INCOMPLETE.value
    elif any(q.get("review_pending") for q in per_question):
        status = FinalScoreStatus.PENDING_REVIEW.value
    else:
        status = FinalScoreStatus.COMPLETE.value
    return total, pct, status


def answer_final(db: Session, answer: Answer, max_marks: float) -> dict:
    """Determine final marks and status for a single answer."""
    cases = list(answer.review_cases)
    resolved = next((c for c in cases if c.status == ReviewStatus.RESOLVED and c.reviewer_marks is not None), None)
    pending = any(c.status in OPEN_STATES for c in cases)
    ev = db.scalar(
        select(Evaluation)
        .where(Evaluation.answer_id == answer.id)
        .order_by(Evaluation.submitted_at.desc())
        .limit(1)
    )
    if resolved:
        return {
            "marks": resolved.reviewer_marks,
            "source": "REVIEWER",
            "review_pending": False,
            "faculty_marks": ev.marks_awarded if ev else None,
        }
    if ev and ev.marks_awarded is not None:
        return {
            "marks": ev.marks_awarded,
            "source": "FACULTY",
            "review_pending": pending,
            "faculty_marks": ev.marks_awarded,
        }
    return {
        "marks": None,
        "source": None,
        "review_pending": pending,
        "faculty_marks": None,
    }


def student_result(db: Session, exam: Examination, student: Student) -> dict:
    """Calculate and return student result dictionary."""
    qs = list(
        db.scalars(
            select(Question)
            .where(Question.examination_id == exam.id)
            .order_by(Question.question_number)
        )
    )
    answers = {
        a.question_id: a
        for a in db.scalars(
            select(Answer)
            .join(AnswerSheet, AnswerSheet.id == Answer.answer_sheet_id)
            .where(
                AnswerSheet.examination_id == exam.id,
                AnswerSheet.student_id == student.id,
            )
        )
    }
    rows = []
    for q in qs:
        a = answers.get(q.id)
        f = answer_final(db, a, q.max_marks) if a else {
            "marks": None,
            "source": None,
            "review_pending": False,
            "faculty_marks": None,
        }
        rows.append({
            "question_number": q.question_number,
            "question_id": str(q.id),
            "max_marks": q.max_marks,
            "answer_id": str(a.id) if a else None,
            **f,
        })
    maximum = round(sum(q.max_marks for q in qs), 2)
    total, pct, status = aggregate(rows, maximum)
    return {
        "student_id": str(student.id),
        "register_number": student.register_number,
        "name": student.name,
        "division": student.division,
        "questions": rows,
        "total_marks": total,
        "maximum_marks": maximum,
        "percentage": pct,
        "status": status,
        "reviewed_answers": sum(1 for r in rows if r["source"] == "REVIEWER"),
    }


def calculate_results(db: Session, exam_id: str, actor_id: Optional[str] = None, student_id: Optional[str] = None) -> list[dict]:
    """Calculate and persist results for all or a single student in an exam."""
    exam = db.get(Examination, exam_id)
    if exam is None:
        raise LookupError("Examination not found")

    scores = calculate_examination_scores(db, exam_id, actor_id=actor_id)
    results = []
    for s in scores:
        if student_id and s.student_id != student_id:
            continue
        student = s.student
        results.append(student_result(db, exam, student))
    return results


def recalc_for_answer(db: Session, answer_id: str, actor_id: Optional[str] = None) -> None:
    """Recalculate score for the student who submitted this answer."""
    a = db.get(Answer, answer_id)
    if a and a.answer_sheet:
        calculate_student_score(db, a.answer_sheet.examination_id, a.answer_sheet.student_id, auto_commit=True)
