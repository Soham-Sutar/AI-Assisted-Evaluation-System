"""Key-point (rubric) coverage. Uses the rubric when present, otherwise the model answer's sentences."""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from app.ai.embeddings import EmbeddingProvider


def normalize_text(text: str) -> str:
    """OCR normalisation: unify whitespace/quotes, drop stray symbols, re-join hyphenated line breaks."""
    t = (text or "").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    t = re.sub(r"-\s*\n\s*", "", t)
    t = re.sub(r"[^\w\s.,;:'()\-%/+=?!]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def split_chunks(text: str, window_words: int = 14) -> list[str]:
    """Sentence-ish chunks plus sliding windows (OCR text often has no reliable punctuation)."""
    t = normalize_text(text)
    if not t:
        return []
    sents = [s.strip() for s in re.split(r"(?<=[.!?;])\s+", t) if len(s.split()) >= 2]
    words = t.split()
    chunks = list(sents)
    step = max(window_words // 2, 4)
    for i in range(0, max(len(words) - window_words, 0) + step, step):
        w = " ".join(words[i:i + window_words])
        if w:
            chunks.append(w)
    chunks.append(t)  # whole answer as a final candidate
    seen, out = set(), []
    for c in chunks:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def model_keypoints(model_answer: str) -> list[dict]:
    sents = [s.strip() for s in re.split(r"(?<=[.!?;])\s+", normalize_text(model_answer)) if len(s.split()) >= 3]
    return [{"description": s, "marks": 1.0} for s in sents] or (
        [{"description": normalize_text(model_answer), "marks": 1.0}] if model_answer else [])


@dataclass
class KeypointResult:
    score: float  # 0-1 weighted coverage
    details: list[dict]
    source: str  # "rubric" | "model_answer_sentences"


def keypoint_coverage(student_text: str, model_answer: str, rubric: dict | None,
                      provider: EmbeddingProvider) -> KeypointResult:
    points = []
    source = "model_answer_sentences"
    if rubric and rubric.get("points"):
        points = [{"description": p["description"], "marks": float(p["marks"])} for p in rubric["points"]
                  if p.get("description") and float(p.get("marks", 0)) > 0]
        source = "rubric"
    if not points:
        points = model_keypoints(model_answer)
    if not points:
        return KeypointResult(0.0, [], "none")
    chunks = split_chunks(student_text)
    if not chunks:
        return KeypointResult(0.0, [{"description": p["description"], "marks": p["marks"], "coverage": 0.0,
                                     "status": "not covered", "similarity": 0.0} for p in points], source)
    sim = provider.similarity([p["description"] for p in points], chunks)
    total = sum(p["marks"] for p in points)
    details, acc = [], 0.0
    for i, p in enumerate(points):
        best = float(np.max(sim[i]))
        cov = float(np.clip((best - provider.pt_lo) / (provider.pt_hi - provider.pt_lo), 0.0, 1.0))
        status = "covered" if cov >= 0.7 else "partially covered" if cov >= 0.35 else "not covered"
        details.append({"description": p["description"], "marks": p["marks"], "similarity": round(best, 3),
                        "coverage": round(cov, 3), "status": status})
        acc += p["marks"] * cov
    return KeypointResult(round(acc / total, 4) if total else 0.0, details, source)
