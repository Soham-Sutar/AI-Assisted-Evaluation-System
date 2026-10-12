"""Runs the independent AI evaluation for an answer AFTER the faculty evaluation is submitted.
AI failure never blocks the human evaluation; it is recorded as a FAILED AIEvaluation."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.ai.embeddings import get_embedding_provider
from app.ai.scorer import InsufficientTextError, evaluate_answer
from app.core.config import get_settings
from app.models import AIEvaluation, Answer
from app.services.audit_service import log_action
from app.services.discrepancy_service import check_and_flag
from app.services.segmentation_service import strip_marker_prefix

log = logging.getLogger("evalai.ai")


def run_ai_evaluation(db: Session, answer_id: uuid.UUID, actor_id: uuid.UUID | None = None) -> AIEvaluation:
    s = get_settings()
    answer = db.get(Answer, answer_id)
    if answer is None:
        raise ValueError("Answer not found")
    q = answer.question
    ai = AIEvaluation(answer_id=answer.id)
    try:
        provider = get_embedding_provider()
        ai.model_name = provider.name
        text = strip_marker_prefix(answer.extracted_text or "")
        res = evaluate_answer(text, q.model_answer_text or "", q.max_marks, q.rubric_json,
                              ocr_confidence=answer.ocr_confidence, text_human_verified=answer.ocr_corrected,
                              semantic_weight=s.ai_semantic_weight, keypoint_weight=s.ai_keypoint_weight,
                              provider=provider)
        ai.status = "COMPLETED"
        ai.ai_marks = res.ai_marks
        ai.final_ai_score = res.final_ai_score
        ai.semantic_similarity = res.semantic_similarity
        ai.keypoint_score = res.keypoint_score
        ai.confidence_score = res.confidence
        ai.explanation_json = res.explanation
        ai.model_name = res.model_name
    except InsufficientTextError as exc:
        ai.status, ai.error_message = "FAILED", str(exc)
        ai.explanation_json = {"failure": str(exc), "fallback": "Manual / image-based human review required."}
    except Exception as exc:  # never let AI problems propagate into the faculty flow
        log.exception("AI evaluation failed for answer %s", answer_id)
        ai.status, ai.error_message = "FAILED", f"{type(exc).__name__}: {exc}"[:300]
        ai.explanation_json = {"failure": ai.error_message}
    db.add(ai)
    log_action(db, actor_id, "ai.evaluated" if ai.status == "COMPLETED" else "ai.failed", "Answer", answer.id,
               {"status": ai.status, "ai_marks": ai.ai_marks, "model": ai.model_name})
    db.commit()
    check_and_flag(db, answer.id)
    return ai


def run_ai_evaluation_background(answer_id: uuid.UUID) -> None:
    """Entry point for FastAPI BackgroundTasks: owns its DB session."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        run_ai_evaluation(db, answer_id)
    except Exception:
        log.exception("Background AI evaluation crashed for %s", answer_id)
    finally:
        db.close()
