import csv
import io
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models.examination import Examination, ExamStatus
from app.models.student import Student
from app.models.question import Question
from app.models.answer_sheet import AnswerSheet
from app.models.answer import Answer
from app.models.evaluation import Evaluation
from app.models.review_case import ReviewCase, ReviewStatus
from app.models.final_score import FinalScore, FinalScoreStatus
from app.schemas.result import (
    QuestionScoreBreakdown,
    StudentResultResponse,
    ExamQuestionSummary,
    ExamResultsResponse,
)
from app.services.audit_service import log_action

logger = logging.getLogger("evalai.scoring")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def calculate_student_score(
    db: Session,
    examination_id: str,
    student_id: str,
    auto_commit: bool = True,
) -> Tuple[FinalScore, List[Dict[str, Any]]]:
    """
    Calculate final score for a specific student in an examination.
    
    Rules:
      1. Reviewed answer with resolved review case -> reviewer marks.
      2. Normal evaluated answer -> faculty marks.
      3. AI marks are advisory and never automatically become final marks.
      4. Missing, unevaluated, or invalid marks are not silently replaced with zero (marks=None, status=INCOMPLETE).
      5. Active review cases (OPEN, ASSIGNED, ESCALATED) set status to PENDING_REVIEW.
    """
    exam = db.get(Examination, examination_id)
    if not exam:
        raise ValueError(f"Examination with ID '{examination_id}' not found")

    student = db.get(Student, student_id)
    if not student:
        raise ValueError(f"Student with ID '{student_id}' not found")

    questions = db.scalars(
        select(Question)
        .where(Question.examination_id == examination_id)
        .order_by(Question.question_number)
    ).all()
    maximum_marks = round(sum(q.max_marks for q in questions), 2)

    sheet = db.scalars(
        select(AnswerSheet).where(
            AnswerSheet.examination_id == examination_id,
            AnswerSheet.student_id == student_id,
        )
    ).first()

    answers_by_qid = {}
    if sheet:
        answers = db.scalars(
            select(Answer).where(Answer.answer_sheet_id == sheet.id)
        ).all()
        answers_by_qid = {a.question_id: a for a in answers}

    breakdown: List[Dict[str, Any]] = []
    has_missing_marks = False
    has_pending_review = False
    reviewed_count = 0

    for q in questions:
        ans = answers_by_qid.get(q.id)
        marks_awarded: Optional[float] = None
        source: Optional[str] = None
        is_reviewed = False
        review_pending = False
        faculty_marks: Optional[float] = None
        reviewer_marks: Optional[float] = None
        ai_marks: Optional[float] = None

        if ans:
            # Check latest AI evaluation marks for reference (never used as final score)
            if ans.latest_ai_evaluation:
                ai_marks = ans.latest_ai_evaluation.ai_marks

            # Check review cases
            cases = list(ans.review_cases)
            resolved_case = next(
                (c for c in cases if c.status == ReviewStatus.RESOLVED and c.reviewer_marks is not None),
                None,
            )
            active_review = any(
                c.status in [ReviewStatus.OPEN, ReviewStatus.ASSIGNED, ReviewStatus.ESCALATED]
                for c in cases
            )

            if active_review:
                review_pending = True
                has_pending_review = True

            # Check faculty evaluation
            fac_eval = db.scalars(
                select(Evaluation)
                .where(Evaluation.answer_id == ans.id)
                .order_by(Evaluation.submitted_at.desc())
            ).first()
            if fac_eval and fac_eval.marks_awarded is not None:
                faculty_marks = fac_eval.marks_awarded

            # Scoring precedence:
            # 1. Resolved reviewer marks take precedence
            if resolved_case:
                marks_awarded = resolved_case.reviewer_marks
                reviewer_marks = resolved_case.reviewer_marks
                source = "REVIEWER"
                is_reviewed = True
                reviewed_count += 1
            # 2. Submitted faculty marks
            elif faculty_marks is not None:
                marks_awarded = faculty_marks
                source = "FACULTY"
                is_reviewed = False
            # 3. Missing/unevaluated
            else:
                marks_awarded = None
                source = None
                is_reviewed = False
                has_missing_marks = True

            # Persist answer-level final marks if columns exist
            ans.final_marks = marks_awarded
            ans.final_marks_source = source

        else:
            # Answer does not exist for this question
            marks_awarded = None
            source = None
            has_missing_marks = True

        breakdown.append({
            "question_id": q.id,
            "question_number": q.question_number,
            "question_text": q.question_text,
            "max_marks": q.max_marks,
            "answer_id": ans.id if ans else None,
            "marks_awarded": marks_awarded,
            "source": source,
            "is_reviewed": is_reviewed,
            "review_pending": review_pending,
            "faculty_marks": faculty_marks,
            "reviewer_marks": reviewer_marks,
            "ai_marks": ai_marks,
        })

    # Status determination:
    if has_missing_marks or not sheet:
        score_status = FinalScoreStatus.INCOMPLETE
    elif has_pending_review:
        score_status = FinalScoreStatus.PENDING_REVIEW
    else:
        score_status = FinalScoreStatus.COMPLETE

    total_marks = round(
        sum(row["marks_awarded"] for row in breakdown if row["marks_awarded"] is not None),
        2,
    )
    percentage = round(total_marks / maximum_marks * 100, 2) if maximum_marks > 0 else 0.0

    # Upsert FinalScore record
    final_score = db.scalars(
        select(FinalScore).where(
            FinalScore.examination_id == examination_id,
            FinalScore.student_id == student_id,
        )
    ).first()

    if not final_score:
        final_score = FinalScore(
            examination_id=examination_id,
            student_id=student_id,
            total_marks=total_marks,
            maximum_marks=maximum_marks,
            percentage=percentage,
            status=score_status,
            breakdown_json=breakdown,
            calculated_at=utc_now(),
        )
        db.add(final_score)
    else:
        final_score.total_marks = total_marks
        final_score.maximum_marks = maximum_marks
        final_score.percentage = percentage
        final_score.status = score_status
        final_score.breakdown_json = breakdown
        final_score.calculated_at = utc_now()

    if auto_commit:
        db.commit()
        db.refresh(final_score)

    return final_score, breakdown


def calculate_examination_scores(
    db: Session,
    examination_id: str,
    actor_id: Optional[str] = None,
) -> List[FinalScore]:
    """
    Calculate and persist FinalScore records for all students in an examination.
    Refreshes examination status based on completion and unresolved reviews.
    """
    exam = db.get(Examination, examination_id)
    if not exam:
        raise ValueError(f"Examination with ID '{examination_id}' not found")

    sheets = db.scalars(
        select(AnswerSheet).where(AnswerSheet.examination_id == examination_id)
    ).all()

    final_scores: List[FinalScore] = []
    for sheet in sheets:
        fs, _ = calculate_student_score(
            db,
            examination_id=examination_id,
            student_id=sheet.student_id,
            auto_commit=False,
        )
        final_scores.append(fs)

    # Check for active unresolved review cases for this exam
    open_cases = db.scalars(
        select(ReviewCase.id)
        .join(Answer, Answer.id == ReviewCase.answer_id)
        .join(AnswerSheet, AnswerSheet.id == Answer.answer_sheet_id)
        .where(
            AnswerSheet.examination_id == examination_id,
            ReviewCase.status.in_([ReviewStatus.OPEN, ReviewStatus.ASSIGNED, ReviewStatus.ESCALATED]),
        )
    ).first()

    # Examination lifecycle update
    if open_cases:
        exam.status = ExamStatus.REVIEW
    elif final_scores and all(s.status == FinalScoreStatus.COMPLETE for s in final_scores):
        exam.status = ExamStatus.COMPLETED
    elif exam.status in [ExamStatus.REVIEW, ExamStatus.COMPLETED]:
        exam.status = ExamStatus.EVALUATION

    db.commit()
    for s in final_scores:
        db.refresh(s)
    db.refresh(exam)

    log_action(
        db,
        user_id=actor_id,
        action="results.calculated",
        entity_type="Examination",
        entity_id=examination_id,
        metadata={
            "student_count": len(final_scores),
            "exam_status": exam.status.value,
        },
    )

    return final_scores


def get_student_result_response(
    db: Session,
    examination_id: str,
    student_id: str,
) -> StudentResultResponse:
    """Retrieve full result details for a single student."""
    exam = db.get(Examination, examination_id)
    if not exam:
        raise ValueError(f"Examination with ID '{examination_id}' not found")

    student = db.get(Student, student_id)
    if not student:
        raise ValueError(f"Student with ID '{student_id}' not found")

    # Ensure score record is computed
    final_score = db.scalars(
        select(FinalScore).where(
            FinalScore.examination_id == examination_id,
            FinalScore.student_id == student_id,
        )
    ).first()

    if not final_score:
        final_score, breakdown = calculate_student_score(db, examination_id, student_id)
    else:
        breakdown = final_score.breakdown_json or []

    questions = [QuestionScoreBreakdown(**row) for row in breakdown]
    reviewed_answers = sum(1 for q in questions if q.source == "REVIEWER")

    return StudentResultResponse(
        student_id=student.id,
        register_number=student.register_number,
        name=student.name,
        division=student.division,
        examination_id=exam.id,
        exam_name=exam.name,
        total_marks=final_score.total_marks,
        maximum_marks=final_score.maximum_marks,
        percentage=final_score.percentage,
        status=final_score.status,
        reviewed_answers=reviewed_answers,
        questions=questions,
        calculated_at=final_score.calculated_at,
    )


def get_examination_results_response(
    db: Session,
    examination_id: str,
    search: Optional[str] = None,
    division: Optional[str] = None,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> ExamResultsResponse:
    """Retrieve examination results summary with filtering and statistics."""
    exam = db.get(Examination, examination_id)
    if not exam:
        raise ValueError(f"Examination with ID '{examination_id}' not found")

    exam_questions = db.scalars(
        select(Question)
        .where(Question.examination_id == examination_id)
        .order_by(Question.question_number)
    ).all()
    q_summaries = [
        ExamQuestionSummary(
            id=q.id,
            question_number=q.question_number,
            question_text=q.question_text,
            max_marks=q.max_marks,
        )
        for q in exam_questions
    ]

    # Query FinalScore records
    stmt = (
        select(FinalScore)
        .join(Student, Student.id == FinalScore.student_id)
        .where(FinalScore.examination_id == examination_id)
    )

    if division:
        stmt = stmt.where(Student.division == division)
    if status_filter:
        stmt = stmt.where(FinalScore.status == status_filter)
    if search:
        search_term = f"%{search.strip()}%"
        stmt = stmt.where(
            (Student.name.ilike(search_term)) | (Student.register_number.ilike(search_term))
        )

    all_scores = db.scalars(stmt).all()
    total_students = len(all_scores)

    completed_count = sum(1 for s in all_scores if s.status == FinalScoreStatus.COMPLETE)
    pending_count = sum(1 for s in all_scores if s.status == FinalScoreStatus.PENDING_REVIEW)
    incomplete_count = sum(1 for s in all_scores if s.status == FinalScoreStatus.INCOMPLETE)

    avg_marks = (
        round(sum(s.total_marks for s in all_scores) / total_students, 2)
        if total_students > 0
        else None
    )

    # Paginate
    paged_scores = all_scores[skip : skip + limit]
    student_results: List[StudentResultResponse] = []
    for s in paged_scores:
        student = s.student
        questions_breakdown = [QuestionScoreBreakdown(**row) for row in (s.breakdown_json or [])]
        reviewed_answers = sum(1 for q in questions_breakdown if q.source == "REVIEWER")
        student_results.append(
            StudentResultResponse(
                student_id=student.id,
                register_number=student.register_number,
                name=student.name,
                division=student.division,
                examination_id=exam.id,
                exam_name=exam.name,
                total_marks=s.total_marks,
                maximum_marks=s.maximum_marks,
                percentage=s.percentage,
                status=s.status,
                reviewed_answers=reviewed_answers,
                questions=questions_breakdown,
                calculated_at=s.calculated_at,
            )
        )

    return ExamResultsResponse(
        examination_id=exam.id,
        exam_name=exam.name,
        status=exam.status.value,
        total_marks=exam.total_marks,
        questions=q_summaries,
        results=student_results,
        total_students=total_students,
        completed_students=completed_count,
        pending_review_students=pending_count,
        incomplete_students=incomplete_count,
        average_marks=avg_marks,
    )


def export_examination_results_csv(
    db: Session,
    examination_id: str,
) -> str:
    """Generate CSV text for examination results export."""
    exam = db.get(Examination, examination_id)
    if not exam:
        raise ValueError(f"Examination with ID '{examination_id}' not found")

    questions = db.scalars(
        select(Question)
        .where(Question.examination_id == examination_id)
        .order_by(Question.question_number)
    ).all()
    q_numbers = [q.question_number for q in questions]

    scores = db.scalars(
        select(FinalScore)
        .join(Student, Student.id == FinalScore.student_id)
        .where(FinalScore.examination_id == examination_id)
        .order_by(Student.register_number)
    ).all()

    buf = io.StringIO()
    writer = csv.writer(buf)

    # CSV Header
    header = (
        ["register_number", "student_name", "division"]
        + [f"Q{num}" for num in q_numbers]
        + ["total_marks", "maximum_marks", "percentage", "status", "reviewed_answers"]
    )
    writer.writerow(header)

    for s in scores:
        student = s.student
        breakdown_by_qnum = {
            row["question_number"]: row["marks_awarded"]
            for row in (s.breakdown_json or [])
        }
        reviewed_count = sum(
            1 for row in (s.breakdown_json or []) if row.get("source") == "REVIEWER"
        )

        row_vals = [
            student.register_number,
            student.name,
            student.division or "",
        ]
        for q_num in q_numbers:
            m = breakdown_by_qnum.get(q_num)
            row_vals.append("" if m is None else str(m))

        row_vals.extend([
            str(s.total_marks),
            str(s.maximum_marks),
            f"{s.percentage}%",
            s.status.value,
            str(reviewed_count),
        ])
        writer.writerow(row_vals)

    return buf.getvalue()
