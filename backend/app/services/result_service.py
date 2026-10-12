"""Final-score aggregation from real DB records.
Per answer: resolved review -> reviewer marks; otherwise submitted faculty marks. AI never contributes."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (Answer, AnswerSheet, Evaluation, Examination, FinalScore, Question, ReviewCase, ReviewStatus,
                        Student)
from app.services.audit_service import log_action
from app.services.discrepancy_service import OPEN_STATES


def aggregate(per_question: list[dict], maximum: float) -> tuple[float, float, str]:
    """Pure function (unit-tested). per_question items: {marks: float|None, review_pending: bool}.
    Returns (total, percentage, status)."""
    total = round(sum(q["marks"] for q in per_question if q["marks"] is not None), 2)
    pct = round(total / maximum * 100, 2) if maximum else 0.0
    if any(q["marks"] is None for q in per_question):
        status = "INCOMPLETE"
    elif any(q.get("review_pending") for q in per_question):
        status = "PENDING_REVIEW"
    else:
        status = "COMPLETE"
    return total, pct, status


def answer_final(db: Session, answer: Answer, max_marks: float) -> dict:
    cases = list(db.scalars(select(ReviewCase).where(ReviewCase.answer_id == answer.id)
                            .order_by(ReviewCase.created_at.desc())))
    resolved = next((c for c in cases if c.status == ReviewStatus.RESOLVED and c.reviewer_marks is not None), None)
    pending = any(c.status in OPEN_STATES for c in cases)
    ev = db.scalar(select(Evaluation).where(Evaluation.answer_id == answer.id, Evaluation.is_draft.is_(False))
                   .order_by(Evaluation.version.desc()).limit(1))
    if resolved:
        return {"marks": resolved.reviewer_marks, "source": "REVIEWER", "review_pending": False,
                "faculty_marks": ev.marks_awarded if ev else None}
    if ev:
        return {"marks": ev.marks_awarded, "source": "FACULTY", "review_pending": pending, "faculty_marks": ev.marks_awarded}
    return {"marks": None, "source": None, "review_pending": pending, "faculty_marks": None}


def student_result(db: Session, exam: Examination, student: Student) -> dict:
    qs = list(db.scalars(select(Question).where(Question.examination_id == exam.id).order_by(Question.question_number)))
    answers = {a.question_id: a for a in db.scalars(select(Answer).join(AnswerSheet, AnswerSheet.id == Answer.answer_sheet_id)
                                                    .where(AnswerSheet.examination_id == exam.id,
                                                           Answer.student_id == student.id))}
    rows = []
    for q in qs:
        a = answers.get(q.id)
        f = answer_final(db, a, q.max_marks) if a else {"marks": None, "source": None, "review_pending": False,
                                                       "faculty_marks": None}
        rows.append({"question_number": q.question_number, "question_id": str(q.id), "max_marks": q.max_marks,
                     "answer_id": str(a.id) if a else None, **f})
    maximum = sum(q.max_marks for q in qs)
    total, pct, status = aggregate(rows, maximum)
    return {"student_id": str(student.id), "register_number": student.register_number, "name": student.name,
            "division": student.division, "questions": rows, "total_marks": total, "maximum_marks": maximum,
            "percentage": pct, "status": status,
            "reviewed_answers": sum(1 for r in rows if r["source"] == "REVIEWER")}


def calculate_results(db: Session, exam_id: uuid.UUID, actor_id=None, student_id=None) -> list[dict]:
    exam = db.get(Examination, exam_id)
    if exam is None:
        raise LookupError("Examination not found")
    q = select(Student).join(AnswerSheet, AnswerSheet.student_id == Student.id).where(
        AnswerSheet.examination_id == exam_id).distinct().order_by(Student.register_number)
    if student_id:
        q = q.where(Student.id == student_id)
    results = []
    for st in db.scalars(q):
        r = student_result(db, exam, st)
        fs = db.scalar(select(FinalScore).where(FinalScore.student_id == st.id, FinalScore.examination_id == exam_id))
        if fs is None:
            fs = FinalScore(student_id=st.id, examination_id=exam_id, total_marks=0, maximum_marks=0, percentage=0,
                            status="INCOMPLETE")
            db.add(fs)
        from app.models.entities import now
        fs.total_marks, fs.maximum_marks, fs.percentage, fs.status = r["total_marks"], r["maximum_marks"], r["percentage"], r["status"]
        fs.calculated_at = now()
        results.append(r)
    log_action(db, actor_id, "results.calculated", "Examination", exam_id, {"students": len(results)})
    refresh_exam_status(db, exam)
    db.commit()
    return results


def refresh_exam_status(db: Session, exam: Examination) -> None:
    if exam.status in ("DRAFT", "READY"):
        return
    open_cases = db.scalar(select(ReviewCase.id).join(Answer, Answer.id == ReviewCase.answer_id)
                           .join(Question, Question.id == Answer.question_id)
                           .where(Question.examination_id == exam.id, ReviewCase.status.in_(OPEN_STATES)).limit(1))
    scores = list(db.scalars(select(FinalScore).where(FinalScore.examination_id == exam.id)))
    if open_cases:
        exam.status = "REVIEW"
    elif scores and all(s.status == "COMPLETE" for s in scores):
        exam.status = "COMPLETED"
    elif exam.status in ("REVIEW", "COMPLETED"):
        exam.status = "EVALUATION"


def recalc_for_answer(db: Session, answer_id, actor_id=None) -> None:
    a = db.get(Answer, answer_id)
    if a and a.student_id:
        exam_id = db.get(Question, a.question_id).examination_id
        calculate_results(db, exam_id, actor_id, a.student_id)
