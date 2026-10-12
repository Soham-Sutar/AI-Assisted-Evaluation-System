"""Embedding/similarity providers. The model is loaded ONCE (module cache), never per answer.

Primary: sentence-transformers all-MiniLM-L6-v2.
Fallback: scikit-learn TF-IDF (char n-grams + words) cosine similarity - a genuine, deterministic lexical-semantic
signal used only when the transformer model cannot be loaded (e.g. weights not downloadable offline). The provider
actually used is recorded in every AIEvaluation (`model_name`) - the system never pretends MiniLM ran when it did not.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import numpy as np

from app.core.config import get_settings

log = logging.getLogger("evalai.ai")


class EmbeddingProvider(ABC):
    name = "abstract"
    reliability = 1.0  # feeds the confidence heuristic
    # Calibration: raw cosine -> [0,1]. Below `lo` = unrelated, above `hi` = equivalent. Documented in docs/ai-evaluation.md
    sem_lo = 0.2
    sem_hi = 0.8
    pt_lo = 0.2
    pt_hi = 0.7

    @abstractmethod
    def similarity(self, a: list[str], b: list[str]) -> np.ndarray:
        """Cosine similarity matrix of shape (len(a), len(b))."""


class SentenceTransformerProvider(EmbeddingProvider):
    reliability = 1.0
    sem_lo, sem_hi, pt_lo, pt_hi = 0.20, 0.80, 0.30, 0.70

    def __init__(self, model_name: str, device: str = "auto"):
        from sentence_transformers import SentenceTransformer

        kwargs = {} if device == "auto" else {"device": device}
        self.model = SentenceTransformer(model_name, **kwargs)
        self.name = model_name

    def similarity(self, a, b):
        ea = self.model.encode(a, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        eb = self.model.encode(b, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        return np.clip(ea @ eb.T, -1.0, 1.0)


class TfidfProvider(EmbeddingProvider):
    name = "tfidf-char+word (scikit-learn fallback)"
    reliability = 0.65
    sem_lo, sem_hi, pt_lo, pt_hi = 0.10, 0.55, 0.10, 0.45

    def similarity(self, a, b):
        from sklearn.feature_extraction.text import TfidfVectorizer

        corpus = [t or "" for t in list(a) + list(b)]
        mats = []
        for kw in (dict(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True),
                   dict(analyzer="word", ngram_range=(1, 1), sublinear_tf=True, stop_words="english")):
            try:
                v = TfidfVectorizer(**kw).fit(corpus)
                X = v.transform(corpus)
                A, B = X[: len(a)], X[len(a):]
                mats.append((A @ B.T).toarray())  # rows are L2-normalised => dot = cosine
            except ValueError:  # empty vocabulary
                mats.append(np.zeros((len(a), len(b))))
        return 0.5 * mats[0] + 0.5 * mats[1]


_provider: EmbeddingProvider | None = None
_load_error: str | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider, _load_error
    if _provider is not None:
        return _provider
    s = get_settings()
    if s.ai_provider in ("auto", "sentence-transformers"):
        try:
            _provider = SentenceTransformerProvider(s.ai_model_name, s.ai_device)
            log.info("Loaded embedding model %s", s.ai_model_name)
            return _provider
        except Exception as exc:
            _load_error = f"{type(exc).__name__}: {exc}"[:300]
            log.warning("Sentence-transformer unavailable (%s); using TF-IDF fallback", _load_error)
    _provider = TfidfProvider()
    return _provider


def provider_status() -> dict:
    p = get_embedding_provider()
    return {"provider": p.name, "fallback": isinstance(p, TfidfProvider), "load_error": _load_error}


def set_embedding_provider(p: EmbeddingProvider | None):
    global _provider
    _provider = p
