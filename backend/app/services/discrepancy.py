from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.answer import Answer
from app.models.evaluation import Evaluation
from app.models.ai_evaluation import AIEvaluation, AIEvaluationStatus
from app.models.review_case import (
    ReviewCase,
    ReviewTriggerType,
    ReviewStatus,
    ReviewPriority,
)
from app.schemas.review_case import ReviewCaseRead, DiscrepancyCheckResponse

logger = logging.getLogger("evalai.discrepancy")


@dataclass
class DiscrepancyMetrics:
    faculty_marks: float
    ai_marks: float
    max_marks: float
    difference: float
    normalized_difference: float
    absolute_threshold: float
    relative_threshold: float
    is_absolute_exceeded: bool
    is_relative_exceeded: bool
    is_discrepant: bool
    priority: ReviewPriority


def priority_for_discrepancy(difference: float, max_marks: float) -> ReviewPriority:
    """Determine review priority based on discrepancy fraction of maximum marks."""
    ratio = difference / max_marks if max_marks > 0 else 0.0
    if ratio >= 0.40:
        return ReviewPriority.HIGH
    elif ratio >= 0.25:
        return ReviewPriority.MEDIUM
    return ReviewPriority.LOW


def compute_discrepancy(
    faculty_marks: float,
    ai_marks: float,
    max_marks: float,
    abs_threshold: float = 2.0,
    rel_threshold: float = 0.20,
    mode: str = "either",
) -> DiscrepancyMetrics:
    """
    Pure comparison between faculty-awarded marks and AI reference marks.

    Formula:
      difference = |faculty_marks - ai_marks|
      normalized_difference = difference / max_marks
      flagged = difference >= abs_threshold OR normalized_difference >= rel_threshold
    """
    diff = round(abs(faculty_marks - ai_marks), 2)
    norm_diff = round(diff / max_marks, 4) if max_marks > 0 else 0.0

    abs_hit = diff >= abs_threshold - 1e-9
    rel_hit = (max_marks > 0) and (norm_diff >= rel_threshold - 1e-9)

    if mode == "absolute":
        is_discrepant = abs_hit
    elif mode == "relative":
        is_discrepant = rel_hit
    else:  # "either"
        is_discrepant = abs_hit or rel_hit

    priority = priority_for_discrepancy(diff, max_marks)

    return DiscrepancyMetrics(
        faculty_marks=faculty_marks,
        ai_marks=ai_marks,
        max_marks=max_marks,
        difference=diff,
        normalized_difference=norm_diff,
        absolute_threshold=abs_threshold,
        relative_threshold=rel_threshold,
        is_absolute_exceeded=abs_hit,
        is_relative_exceeded=rel_hit,
        is_discrepant=is_discrepant,
        priority=priority,
    )


def enrich_review_case(case: ReviewCase) -> ReviewCaseRead:
    """Enrich ReviewCase model into ReviewCaseRead schema with human-friendly metadata."""
    answer = case.answer
    question = answer.question if answer else None
    faculty_eval = case.faculty_evaluation
    faculty = faculty_eval.faculty if faculty_eval else None
    ai_eval = case.ai_evaluation

    return ReviewCaseRead(
        id=case.id,
        answer_id=case.answer_id,
        faculty_evaluation_id=case.faculty_evaluation_id,
        ai_evaluation_id=case.ai_evaluation_id,
        trigger_type=case.trigger_type,
        discrepancy_value=case.discrepancy_value,
        discrepancy_amount=case.discrepancy_value,
        priority=case.priority,
        status=case.status,
        note=case.note,
        trigger_reason=case.note,
        reviewer_id=case.reviewer_id,
        reviewer_marks=case.reviewer_marks,
        reviewer_comments=case.reviewer_comments,
        created_at=case.created_at,
        resolved_at=case.resolved_at,
        question_number=question.question_number if question else None,
        question_text=question.question_text if question else None,
        max_marks=question.max_marks if question else None,
        faculty_marks=faculty_eval.marks_awarded if faculty_eval else None,
        ai_marks=ai_eval.ai_marks if ai_eval else None,
        faculty_name=faculty.full_name if faculty else None,
    )


def detect_and_create_review_case(
    db: Session,
    answer_id: str,
    abs_threshold: Optional[float] = None,
    rel_threshold: Optional[float] = None,
) -> Tuple[DiscrepancyMetrics, Optional[ReviewCase]]:
    """
    Evaluates discrepancy between completed faculty evaluation and independent AI evaluation.
    If discrepancy policy is met, creates or returns an active ReviewCase.
    Idempotent: avoids duplicate active review cases for repeated checks.
    """
    answer = db.get(Answer, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer with ID '{answer_id}' not found",
        )

    # 1. Verify submitted faculty evaluation
    faculty_eval = db.scalars(
        select(Evaluation)
        .where(Evaluation.answer_id == answer_id)
        .order_by(Evaluation.submitted_at.desc())
    ).first()
    if not faculty_eval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot run discrepancy detection: Faculty evaluation has not been submitted for this answer.",
        )

    # 2. Verify completed independent AI evaluation
    ai_eval = db.scalars(
        select(AIEvaluation)
        .where(AIEvaluation.answer_id == answer_id)
        .order_by(AIEvaluation.created_at.desc())
    ).first()
    if not ai_eval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot run discrepancy detection: AI evaluation has not been performed for this answer.",
        )
    if ai_eval.status != AIEvaluationStatus.COMPLETED or ai_eval.ai_marks is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot run discrepancy detection: AI evaluation status is '{ai_eval.status.value}'. Completed score required.",
        )

    max_marks = float(answer.question.max_marks) if answer.question else float(faculty_eval.max_marks)
    if max_marks <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot run discrepancy detection: Invalid question maximum marks.",
        )

    t_abs = abs_threshold if abs_threshold is not None else settings.DISCREPANCY_ABSOLUTE_THRESHOLD
    t_rel = rel_threshold if rel_threshold is not None else settings.DISCREPANCY_RELATIVE_THRESHOLD

    metrics = compute_discrepancy(
        faculty_marks=faculty_eval.marks_awarded,
        ai_marks=ai_eval.ai_marks,
        max_marks=max_marks,
        abs_threshold=t_abs,
        rel_threshold=t_rel,
    )

    review_case: Optional[ReviewCase] = None

    if metrics.is_discrepant:
        # Check for existing active review case (idempotent, avoid duplicate active cases)
        existing_case = db.scalars(
            select(ReviewCase).where(
                ReviewCase.answer_id == answer_id,
                ReviewCase.trigger_type == ReviewTriggerType.AI_HUMAN_DISCREPANCY,
                ReviewCase.status.in_([ReviewStatus.OPEN, ReviewStatus.ASSIGNED, ReviewStatus.ESCALATED]),
            )
        ).first()

        if existing_case:
            review_case = existing_case
        else:
            review_case = ReviewCase(
                answer_id=answer.id,
                faculty_evaluation_id=faculty_eval.id,
                ai_evaluation_id=ai_eval.id,
                trigger_type=ReviewTriggerType.AI_HUMAN_DISCREPANCY,
                discrepancy_value=metrics.difference,
                priority=metrics.priority,
                status=ReviewStatus.OPEN,
                note=(
                    f"Significant score discrepancy detected: faculty score {faculty_eval.marks_awarded} "
                    f"vs AI reference score {ai_eval.ai_marks} (difference {metrics.difference}/{max_marks}). "
                    "Potential evaluation inconsistency flagged for review."
                ),
            )
            db.add(review_case)
            db.commit()
            db.refresh(review_case)
            logger.info(
                "Review case created: %s for answer %s (diff=%s, priority=%s)",
                review_case.id,
                answer.id,
                metrics.difference,
                metrics.priority,
            )
    else:
        # Check if an active case exists from prior check
        review_case = db.scalars(
            select(ReviewCase).where(
                ReviewCase.answer_id == answer_id,
                ReviewCase.trigger_type == ReviewTriggerType.AI_HUMAN_DISCREPANCY,
                ReviewCase.status.in_([ReviewStatus.OPEN, ReviewStatus.ASSIGNED, ReviewStatus.ESCALATED]),
            )
        ).first()

    return metrics, review_case
