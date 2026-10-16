"""Analytics computed from real DB rows only. Neutral wording: 'evaluation pattern', never 'biased'."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional, List, Dict, Any

from sqlalchemy import func, select, and_
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.student import Student
from app.models.examination import Examination
from app.models.question import Question
from app.models.answer_sheet import AnswerSheet, ProcessingStatus
from app.models.answer import Answer, SegmentationStatus
from app.models.assignment import Assignment, AssignmentStatus
from app.models.evaluation import Evaluation
from app.models.ai_evaluation import AIEvaluation, AIEvaluationStatus
from app.models.review_case import ReviewCase, ReviewStatus
from app.models.final_score import FinalScore

logger = logging.getLogger("evalai.analytics")

OPEN_STATES = [ReviewStatus.OPEN, ReviewStatus.ASSIGNED]


def _count(db: Session, stmt) -> int:
    return db.scalar(stmt) or 0


def overview(db: Session) -> dict:
    total_answers = _count(db, select(func.count(Answer.id)))
    submitted = _count(db, select(func.count(func.distinct(Evaluation.answer_id))))
    return {
        "total_students": _count(db, select(func.count(Student.id))),
        "total_answer_sheets": _count(db, select(func.count(AnswerSheet.id))),
        "processed_sheets": _count(
            db,
            select(func.count(AnswerSheet.id)).where(
                AnswerSheet.processing_status.in_(
                    [ProcessingStatus.PROCESSED, ProcessingStatus.REVIEW_REQUIRED]
                )
            ),
        ),
        "total_answers": total_answers,
        "answers_needing_correction": _count(
            db,
            select(func.count(Answer.id)).where(
                Answer.status == SegmentationStatus.NEEDS_REVIEW
            ),
        ),
        "pending_evaluations": _count(
            db,
            select(func.count(Assignment.id)).where(
                Assignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS])
            ),
        ),
        "completed_evaluations": submitted,
        "flagged_discrepancies": _count(db, select(func.count(ReviewCase.id))),
        "open_reviews": _count(
            db, select(func.count(ReviewCase.id)).where(ReviewCase.status.in_(OPEN_STATES))
        ),
        "resolved_reviews": _count(
            db, select(func.count(ReviewCase.id)).where(ReviewCase.status == ReviewStatus.RESOLVED)
        ),
        "evaluation_completion_rate": round(submitted / total_answers * 100, 1)
        if total_answers
        else 0.0,
    }


def faculty_workload(db: Session, exam_id: Optional[str] = None) -> list[dict]:
    rows = []
    faculty_members = db.scalars(
        select(User).where(User.role == UserRole.FACULTY).order_by(User.full_name)
    ).all()

    for f in faculty_members:
        q = select(Assignment.status, func.count(Assignment.id)).where(
            Assignment.faculty_id == f.id
        )
        if exam_id:
            q = (
                q.join(Answer, Answer.id == Assignment.answer_id)
                .join(Question, Question.id == Answer.question_id)
                .where(Question.examination_id == str(exam_id))
            )
        counts = dict(db.execute(q.group_by(Assignment.status)).all())
        active = counts.get(AssignmentStatus.ASSIGNED, 0) + counts.get(
            AssignmentStatus.IN_PROGRESS, 0
        )
        completed = counts.get(AssignmentStatus.COMPLETED, 0)
        rows.append(
            {
                "faculty_id": str(f.id),
                "name": f.full_name,
                "active": active,
                "completed": completed,
                "capacity": 40,
                "available": f.is_active,
                "is_active": f.is_active,
            }
        )
    return rows


def exam_analytics(db: Session, exam_id: str) -> dict:
    exam = db.get(Examination, str(exam_id))
    if exam is None:
        raise LookupError("Examination not found")

    qs = list(
        db.scalars(
            select(Question)
            .where(Question.examination_id == str(exam_id))
            .order_by(Question.question_number)
        )
    )
    answers = (
        list(db.scalars(select(Answer).where(Answer.question_id.in_([q.id for q in qs]))))
        if qs
        else []
    )
    answer_ids = [a.id for a in answers]

    evals = {}
    if answer_ids:
        for ev in db.scalars(
            select(Evaluation).where(Evaluation.answer_id.in_(answer_ids)).order_by(Evaluation.version)
        ):
            evals[ev.answer_id] = ev

    scores = list(
        db.scalars(select(FinalScore).where(FinalScore.examination_id == str(exam_id)))
    )

    # Score distribution in 10 percentage buckets
    buckets = [0] * 10
    for s in scores:
        if s.percentage is not None:
            buckets[min(int(s.percentage // 10), 9)] += 1
    distribution = [
        {"range": f"{i * 10}-{i * 10 + 10 if i < 9 else 100}%", "students": buckets[i]}
        for i in range(10)
    ]

    # Per-question stats
    qstats = []
    by_q = defaultdict(list)
    for a in answers:
        if a.id in evals:
            by_q[a.question_id].append(evals[a.id].marks_awarded)
    for q in qs:
        m = by_q.get(q.id, [])
        qstats.append(
            {
                "question_number": q.question_number,
                "max_marks": q.max_marks,
                "evaluated": len(m),
                "average_marks": round(sum(m) / len(m), 2) if m else None,
                "average_pct": round(sum(m) / len(m) / q.max_marks * 100, 1) if m else None,
            }
        )

    # Faculty vs AI comparison / evaluation patterns (neutral language)
    pairs, per_faculty = [], defaultdict(
        lambda: {
            "evaluated": 0,
            "compared": 0,
            "signed_diff": 0.0,
            "abs_diff": 0.0,
            "flagged": 0,
            "marks": [],
        }
    )
    flagged_answers = (
        set(
            db.scalars(
                select(ReviewCase.answer_id).where(ReviewCase.answer_id.in_(answer_ids))
            ).all()
        )
        if answer_ids
        else set()
    )

    for a in answers:
        ev = evals.get(a.id)
        if not ev:
            continue
        pf = per_faculty[ev.faculty_id]
        pf["evaluated"] += 1
        if ev.max_marks > 0:
            pf["marks"].append(ev.marks_awarded / ev.max_marks)

        latest_ai = db.scalars(
            select(AIEvaluation)
            .where(AIEvaluation.answer_id == a.id)
            .order_by(AIEvaluation.created_at.desc())
        ).first()

        if latest_ai and latest_ai.status == AIEvaluationStatus.COMPLETED and latest_ai.ai_marks is not None:
            d = ev.marks_awarded - latest_ai.ai_marks
            pf["compared"] += 1
            pf["signed_diff"] += d
            pf["abs_diff"] += abs(d)
            pairs.append(
                {
                    "answer_id": str(a.id),
                    "question_number": a.question.question_number if a.question else None,
                    "faculty_marks": ev.marks_awarded,
                    "ai_marks": latest_ai.ai_marks,
                    "difference": round(d, 2),
                }
            )

        if a.id in flagged_answers:
            pf["flagged"] += 1

    names = {
        u.id: u.full_name
        for u in db.scalars(select(User).where(User.id.in_(list(per_faculty.keys()) or ["none"])))
    }
    patterns = []
    for fid, pf in per_faculty.items():
        c = pf["compared"]
        patterns.append(
            {
                "faculty_id": str(fid),
                "name": names.get(fid, "Unknown"),
                "evaluated": pf["evaluated"],
                "compared_with_ai": c,
                "mean_difference_vs_ai": round(pf["signed_diff"] / c, 2) if c else None,
                "mean_abs_difference_vs_ai": round(pf["abs_diff"] / c, 2) if c else None,
                "discrepancy_flags": pf["flagged"],
                "discrepancy_rate_pct": round(pf["flagged"] / pf["evaluated"] * 100, 1)
                if pf["evaluated"]
                else 0.0,
                "mean_awarded_pct": round(sum(pf["marks"]) / len(pf["marks"]) * 100, 1)
                if pf["marks"]
                else 0.0,
                "note": "Evaluation pattern indicator only; not evidence of intent. Small samples are not meaningful.",
            }
        )

    n_ans = len(answers)
    return {
        "exam": {"id": str(exam.id), "name": exam.name, "status": exam.status.value},
        "students": _count(
            db,
            select(func.count(func.distinct(AnswerSheet.student_id))).where(
                AnswerSheet.examination_id == str(exam_id)
            ),
        ),
        "sheets": _count(
            db, select(func.count(AnswerSheet.id)).where(AnswerSheet.examination_id == str(exam_id))
        ),
        "answers": n_ans,
        "evaluated_answers": len(evals),
        "completion_rate": round(len(evals) / n_ans * 100, 1) if n_ans else 0.0,
        "average_total_marks": round(sum(s.total_marks for s in scores) / len(scores), 2)
        if scores
        else None,
        "average_percentage": round(sum(s.percentage for s in scores) / len(scores), 1)
        if scores
        else None,
        "score_distribution": distribution,
        "question_stats": qstats,
        "faculty_workload": faculty_workload(db, exam_id),
        "evaluation_patterns": patterns,
        "discrepancy_distribution": discrepancy_distribution(db, str(exam_id)),
        "faculty_vs_ai": pairs,
    }


def discrepancy_distribution(db: Session, exam_id: str) -> list[dict]:
    rows = db.execute(
        select(ReviewCase.priority, ReviewCase.status, func.count(ReviewCase.id))
        .join(Answer, Answer.id == ReviewCase.answer_id)
        .join(Question, Question.id == Answer.question_id)
        .where(Question.examination_id == str(exam_id))
        .group_by(ReviewCase.priority, ReviewCase.status)
    ).all()
    return [{"priority": p.value if hasattr(p, "value") else str(p),
             "status": s.value if hasattr(s, "value") else str(s),
             "count": c} for p, s, c in rows]


def faculty_summary(db: Session, faculty_id: str) -> dict:
    counts = dict(
        db.execute(
            select(Assignment.status, func.count(Assignment.id))
            .where(Assignment.faculty_id == str(faculty_id))
            .group_by(Assignment.status)
        ).all()
    )
    pending = counts.get(AssignmentStatus.ASSIGNED, 0)
    in_prog = counts.get(AssignmentStatus.IN_PROGRESS, 0)
    done = counts.get(AssignmentStatus.COMPLETED, 0)
    total = pending + in_prog + done
    return {
        "pending": pending,
        "in_progress": in_prog,
        "completed": done,
        "total": total,
        "progress_pct": round(done / total * 100, 1) if total else 0.0,
    }
