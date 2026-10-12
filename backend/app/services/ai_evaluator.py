from __future__ import annotations

import logging
import re
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.answer import Answer
from app.models.ai_evaluation import AIEvaluation, AIEvaluationStatus
from app.ai.embeddings import get_embedding_provider
from app.ai.scorer import evaluate_answer, InsufficientTextError
from app.models.ai_evaluation import utc_now

log = logging.getLogger("evalai.ai")


def strip_marker_prefix(text: str) -> str:
    """Remove leading question markers like Q1, Question 2:, 1., etc."""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"^\s*(?:question|ques|qn|q)[\s.\-_:]*\d{1,2}\s*[.:)\-]?\s*", "", t, flags=re.I)
    t = re.sub(r"^\s*\d{1,2}\s*[.)]\s*", "", t)
    return t.strip()


def evaluate_student_answer(
    db: Session,
    answer_id: str,
    force_reevaluate: bool = False,
) -> AIEvaluation:
    """
    Evaluates an answer independently using student answer text, question text,
    model answer, rubric, and max marks.
    
    CRITICAL: Faculty marks are NEVER used as an input to AI evaluation,
    and faculty evaluations are NEVER altered or overwritten.
    """
    answer = db.get(Answer, answer_id)
    if answer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer with id '{answer_id}' not found",
        )

    # Idempotency: return existing completed evaluation if not forcing re-evaluation
    if not force_reevaluate and answer.ai_evaluations:
        latest = answer.ai_evaluations[0]
        if latest.status == AIEvaluationStatus.COMPLETED:
            return latest

    question = answer.question
    if question is None:
        ai_eval = AIEvaluation(
            answer_id=answer.id,
            status=AIEvaluationStatus.FAILED,
            max_marks=0.0,
            model_name=settings.AI_MODEL_NAME,
            error_message="Question associated with answer not found",
            explanation_json={"failure": "Missing question association"},
            completed_at=utc_now(),
        )
        db.add(ai_eval)
        db.commit()
        db.refresh(ai_eval)
        return ai_eval

    max_marks = float(question.max_marks)
    if max_marks <= 0:
        ai_eval = AIEvaluation(
            answer_id=answer.id,
            status=AIEvaluationStatus.FAILED,
            max_marks=0.0,
            model_name=settings.AI_MODEL_NAME,
            error_message="Question max_marks must be greater than zero",
            explanation_json={"failure": "Invalid question max marks"},
            completed_at=utc_now(),
        )
        db.add(ai_eval)
        db.commit()
        db.refresh(ai_eval)
        return ai_eval

    raw_text = answer.corrected_text or answer.ocr_text or ""
    student_text = strip_marker_prefix(raw_text)

    # Check for empty / insufficient student text
    if len(student_text.split()) < 3:
        ai_eval = AIEvaluation(
            answer_id=answer.id,
            status=AIEvaluationStatus.FAILED,
            max_marks=max_marks,
            model_name=settings.AI_MODEL_NAME,
            error_message="Insufficient or unreadable student text for AI evaluation",
            explanation_json={
                "failure": "Insufficient text",
                "fallback": "Manual / human evaluation required.",
            },
            completed_at=utc_now(),
        )
        db.add(ai_eval)
        db.commit()
        db.refresh(ai_eval)
        return ai_eval

    model_answer = question.model_answer_text or ""
    rubric = question.rubric_json
    if not model_answer.strip() and not (rubric and rubric.get("points")):
        ai_eval = AIEvaluation(
            answer_id=answer.id,
            status=AIEvaluationStatus.FAILED,
            max_marks=max_marks,
            model_name=settings.AI_MODEL_NAME,
            error_message="No reference model answer or rubric configured for question",
            explanation_json={"failure": "Missing model answer and rubric"},
            completed_at=utc_now(),
        )
        db.add(ai_eval)
        db.commit()
        db.refresh(ai_eval)
        return ai_eval

    try:
        provider = get_embedding_provider()
        text_human_verified = bool(answer.corrected_text)
        res = evaluate_answer(
            student_text=student_text,
            model_answer=model_answer,
            max_marks=max_marks,
            rubric=rubric,
            ocr_confidence=answer.ocr_confidence,
            text_human_verified=text_human_verified,
            semantic_weight=settings.AI_SEMANTIC_WEIGHT,
            keypoint_weight=settings.AI_KEYPOINT_WEIGHT,
            provider=provider,
        )

        if res.ai_marks < 0 or res.ai_marks > max_marks:
            raise ValueError(f"AI score {res.ai_marks} out of valid range [0, {max_marks}]")

        ai_eval = AIEvaluation(
            answer_id=answer.id,
            status=AIEvaluationStatus.COMPLETED,
            ai_marks=res.ai_marks,
            max_marks=max_marks,
            final_ai_score=res.final_ai_score,
            semantic_similarity=res.semantic_similarity,
            keypoint_score=res.keypoint_score,
            confidence_score=res.confidence,
            explanation_json=res.explanation,
            model_name=res.model_name,
            completed_at=utc_now(),
        )
    except InsufficientTextError as exc:
        ai_eval = AIEvaluation(
            answer_id=answer.id,
            status=AIEvaluationStatus.FAILED,
            max_marks=max_marks,
            model_name=settings.AI_MODEL_NAME,
            error_message=str(exc),
            explanation_json={"failure": str(exc)},
            completed_at=utc_now(),
        )
    except Exception as exc:
        log.exception("AI evaluation failed for answer %s", answer_id)
        ai_eval = AIEvaluation(
            answer_id=answer.id,
            status=AIEvaluationStatus.FAILED,
            max_marks=max_marks,
            model_name=settings.AI_MODEL_NAME,
            error_message=f"{type(exc).__name__}: {str(exc)}"[:500],
            explanation_json={"failure": f"Inference failure: {type(exc).__name__}"},
            completed_at=utc_now(),
        )

    db.add(ai_eval)
    db.commit()
    db.refresh(ai_eval)
    return ai_eval
