"""Prototype confidence heuristic (NOT a calibrated probability). Documented in docs/ai-evaluation.md."""
from __future__ import annotations


def compute_confidence(ocr_quality: float, semantic: float, keypoint: float, student_words: int, model_words: int,
                       provider_reliability: float) -> tuple[float, dict]:
    """
    ocr_quality  : 0-1 (mean OCR confidence/100; 1.0 if a human corrected the text)
    agreement    : 1 - |semantic - keypoint|  (do the two independent signals agree?)
    length       : student length relative to model answer (very short answers are harder to judge)
    provider     : reliability of the similarity engine (transformer 1.0, TF-IDF fallback lower)
    """
    agreement = 1.0 - abs(semantic - keypoint)
    ratio = student_words / max(model_words, 1)
    length = min(1.0, ratio / 0.5) if ratio < 0.5 else (1.0 if ratio <= 3 else max(0.5, 3 / ratio))
    conf = 0.35 * ocr_quality + 0.25 * agreement + 0.15 * length + 0.25 * provider_reliability
    parts = {"ocr_quality": round(ocr_quality, 3), "signal_agreement": round(agreement, 3),
             "length_adequacy": round(length, 3), "provider_reliability": round(provider_reliability, 3)}
    return round(max(0.0, min(1.0, conf)), 3), parts
