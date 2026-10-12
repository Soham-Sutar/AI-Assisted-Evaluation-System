"""Human-vs-AI discrepancy detection. Neutral language only: a discrepancy is a review signal, not proof of bias."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AIEvaluation, Answer, Evaluation, ReviewCase, ReviewStatus
from app.services.audit_service import log_action
from app.services.settings_service import get_effective

OPEN_STATES = (ReviewStatus.OPEN, ReviewStatus.ASSIGNED, ReviewStatus.ESCALATED)


def compute_discrepancy(faculty_marks: float, ai_marks: float, max_marks: float, abs_threshold: float,
                        rel_threshold: float, mode: str = "absolute") -> tuple[bool, float]:
    """difference = |faculty - ai|. Flagged when difference >= threshold.
    mode: absolute (marks), relative (fraction of max marks) or either."""
    diff = round(abs(faculty_marks - ai_marks), 2)
    abs_hit = diff >= abs_threshold - 1e-9
    rel_hit = max_marks > 0 and (diff / max_marks) >= rel_threshold - 1e-9
    flagged = {"absolute": abs_hit, "relative": rel_hit, "either": abs_hit or rel_hit}.get(mode, abs_hit)
    return flagged, diff


def priority_for(diff: float, max_marks: float) -> str:
    ratio = diff / max_marks if max_marks else 0
    return "HIGH" if ratio >= 0.4 else "MEDIUM" if ratio >= 0.25 else "LOW"


def latest_submitted_evaluation(db: Session, answer_id) -> Evaluation | None:
    return db.scalar(select(Evaluation).where(Evaluation.answer_id == answer_id, Evaluation.is_draft.is_(False))
                     .order_by(Evaluation.version.desc()).limit(1))


def latest_ai_evaluation(db: Session, answer_id) -> AIEvaluation | None:
    return db.scalar(select(AIEvaluation).where(AIEvaluation.answer_id == answer_id)
                     .order_by(AIEvaluation.created_at.desc()).limit(1))


def _existing_case(db: Session, answer_id, trigger: str) -> ReviewCase | None:
    return db.scalar(select(ReviewCase).where(ReviewCase.answer_id == answer_id, ReviewCase.trigger_type == trigger,
                                              ReviewCase.status.in_(OPEN_STATES)))


def check_and_flag(db: Session, answer_id) -> ReviewCase | None:
    """Idempotent. Needs BOTH independent scores. Creates a ReviewCase when the threshold is exceeded, or a
    LOW_AI_CONFIDENCE case when the AI could not evaluate (so the answer is not silently left without a second look)."""
    ev = latest_submitted_evaluation(db, answer_id)
    ai = latest_ai_evaluation(db, answer_id)
    if ev is None or ai is None or ev.marks_awarded is None:
        return None
    cfg = get_effective(db)
    if ai.status != "COMPLETED" or ai.ai_marks is None:
        if _existing_case(db, answer_id, "LOW_AI_CONFIDENCE"):
            return None
        case = ReviewCase(answer_id=answer_id, trigger_type="LOW_AI_CONFIDENCE", priority="LOW",
                          note=f"AI evaluation unavailable: {ai.error_message or 'unknown reason'}. "
                               "Faculty evaluation preserved; human review suggested.")
        db.add(case)
        log_action(db, None, "review.created", "ReviewCase", case.id, {"trigger": "LOW_AI_CONFIDENCE"})
        db.commit()
        return case
    flagged, diff = compute_discrepancy(ev.marks_awarded, ai.ai_marks, ev.max_marks, cfg["review_absolute_threshold"],
                                        cfg["review_relative_threshold"], cfg["review_mode"])
    if not flagged or _existing_case(db, answer_id, "AI_HUMAN_DISCREPANCY"):
        return None
    case = ReviewCase(answer_id=answer_id, trigger_type="AI_HUMAN_DISCREPANCY", discrepancy_value=diff,
                      priority=priority_for(diff, ev.max_marks),
                      note=f"Evaluation discrepancy detected: faculty {ev.marks_awarded} vs AI reference "
                           f"{ai.ai_marks} (difference {diff}). Potential evaluator inconsistency - review suggested.")
    db.add(case)
    log_action(db, None, "review.created", "ReviewCase", case.id,
               {"trigger": "AI_HUMAN_DISCREPANCY", "difference": diff, "answer_id": str(answer_id)})
    db.commit()
    return case
