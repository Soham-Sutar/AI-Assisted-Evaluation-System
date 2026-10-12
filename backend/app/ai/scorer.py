"""AI reference scorer. Pure function of (student text, model answer, rubric, max marks) - it never sees the faculty
score, which is what makes it an independent signal."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.ai.confidence import compute_confidence
from app.ai.embeddings import EmbeddingProvider, get_embedding_provider
from app.ai.rubric import keypoint_coverage, normalize_text


class InsufficientTextError(Exception):
    """Student text is empty / too short to evaluate (e.g. OCR failed or blank answer)."""


@dataclass
class AIResult:
    ai_marks: float
    final_ai_score: float  # normalised 0-1
    semantic_similarity: float  # normalised 0-1
    keypoint_score: float  # 0-1
    confidence: float
    model_name: str
    explanation: dict = field(default_factory=dict)


def evaluate_answer(student_text: str, model_answer: str, max_marks: float, rubric: dict | None = None,
                    ocr_confidence: float | None = None, text_human_verified: bool = False,
                    semantic_weight: float = 0.5, keypoint_weight: float = 0.5,
                    provider: EmbeddingProvider | None = None) -> AIResult:
    provider = provider or get_embedding_provider()
    student = normalize_text(student_text)
    model = normalize_text(model_answer or "")
    if len(student.split()) < 3:
        raise InsufficientTextError("Not enough readable text to evaluate (OCR failed, low quality or blank).")
    if not model and not (rubric and rubric.get("points")):
        raise InsufficientTextError("No model answer or rubric configured for this question.")

    # Stage 1 - semantic similarity (whole answer vs model answer)
    semantic_raw = None
    semantic = 0.0
    if model:
        semantic_raw = float(provider.similarity([student], [model])[0, 0])
        semantic = float(np.clip((semantic_raw - provider.sem_lo) / (provider.sem_hi - provider.sem_lo), 0, 1))
    # Stage 2 - key-point coverage
    kp = keypoint_coverage(student, model, rubric, provider)
    # Stage 3 - weighted combination (weights normalised so they always sum to 1)
    ws, wk = max(semantic_weight, 0.0), max(keypoint_weight, 0.0)
    if not model:  # rubric only -> semantic signal unavailable
        ws, wk = 0.0, 1.0
    if ws + wk == 0:
        ws, wk = 0.5, 0.5
    ws, wk = ws / (ws + wk), wk / (ws + wk)
    normalized = ws * semantic + wk * kp.score
    marks = float(np.clip(round(normalized * max_marks, 1), 0.0, max_marks))

    if ocr_confidence is None and not text_human_verified:
        ocr_q = 0.5
    else:
        ocr_q = 1.0 if text_human_verified else float(np.clip(ocr_confidence / 100.0, 0, 1))
    conf, conf_parts = compute_confidence(ocr_q, semantic, kp.score, len(student.split()), max(len(model.split()), 1),
                                          provider.reliability)
    explanation = {
        "method": "hybrid: semantic similarity + key-point coverage",
        "provider": provider.name,
        "formula": f"normalized = {ws:.2f} * semantic + {wk:.2f} * keypoint; ai_marks = round(normalized * max_marks, 1)",
        "signals": {"semantic_raw_cosine": None if semantic_raw is None else round(semantic_raw, 4),
                    "semantic_normalized": round(semantic, 4), "keypoint_score": kp.score,
                    "keypoint_source": kp.source, "normalized_score": round(normalized, 4)},
        "weights": {"semantic": round(ws, 3), "keypoint": round(wk, 3)},
        "keypoints": kp.details,
        "confidence_components": conf_parts,
        "text_human_verified": text_human_verified,
        "limitations": ["Advisory reference score only - never replaces the faculty score.",
                        "Quality depends on OCR text quality; handwriting OCR can be inaccurate.",
                        "Confidence is a heuristic, not a calibrated probability."],
    }
    return AIResult(marks, round(normalized, 4), round(semantic, 4), kp.score, conf, provider.name, explanation)
