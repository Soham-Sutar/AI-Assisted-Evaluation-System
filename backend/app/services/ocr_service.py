"""OCR behind a provider abstraction (guide section 6): OCRProvider.extract(image) -> OCRResult.

Failure is explicit: an exception becomes status FAILED with an error message; we never fabricate text.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from app.core.config import get_settings


@dataclass
class OCRWord:
    text: str
    conf: float  # 0-100
    x: int
    y: int
    w: int
    h: int
    block: int = 0
    par: int = 0
    line: int = 0


@dataclass
class OCRResult:
    text: str
    confidence: float | None  # mean word confidence 0-100, None if no words
    words: list[OCRWord] = field(default_factory=list)
    status: str = "OK"  # OK | LOW_CONFIDENCE | FAILED | BLANK
    error: str | None = None


class OCRProvider(ABC):
    name = "abstract"

    @abstractmethod
    def extract(self, image: np.ndarray, psm: int = 6, whitelist: str | None = None) -> OCRResult: ...


class TesseractProvider(OCRProvider):
    name = "tesseract"

    def __init__(self, language: str | None = None):
        self.language = language or get_settings().ocr_language

    def extract(self, image: np.ndarray, psm: int = 6, whitelist: str | None = None) -> OCRResult:
        import pytesseract

        cfg = f"--oem 1 --psm {psm}"
        if whitelist:
            cfg += f" -c tessedit_char_whitelist={whitelist}"
        try:
            d = pytesseract.image_to_data(image, lang=self.language, config=cfg, output_type=pytesseract.Output.DICT)
        except Exception as exc:  # tesseract missing, corrupt image, etc.
            return OCRResult(text="", confidence=None, status="FAILED", error=f"{type(exc).__name__}: {exc}")
        words: list[OCRWord] = []
        for i, t in enumerate(d["text"]):
            t = (t or "").strip()
            try:
                conf = float(d["conf"][i])
            except (TypeError, ValueError):
                conf = -1
            if not t or conf < 0:
                continue
            words.append(OCRWord(t, conf, int(d["left"][i]), int(d["top"][i]), int(d["width"][i]),
                                 int(d["height"][i]), int(d["block_num"][i]), int(d["par_num"][i]),
                                 int(d["line_num"][i])))
        text = words_to_text(words)
        if not words:
            return OCRResult(text="", confidence=None, words=[], status="FAILED", error="No text recognised")
        mean = float(np.mean([w.conf for w in words]))
        status = "OK" if mean >= get_settings().ocr_low_confidence else "LOW_CONFIDENCE"
        return OCRResult(text=text, confidence=round(mean, 1), words=words, status=status)


def words_to_text(words: list[OCRWord]) -> str:
    lines: dict[tuple, list[OCRWord]] = {}
    for w in words:
        lines.setdefault((w.block, w.par, w.line), []).append(w)
    out = []
    for key in sorted(lines, key=lambda k: (min(w.y for w in lines[k]), k)):
        out.append(" ".join(w.text for w in sorted(lines[key], key=lambda w: w.x)))
    return "\n".join(out)


_provider: OCRProvider | None = None


def get_ocr_provider() -> OCRProvider:
    global _provider
    if _provider is None:
        _provider = TesseractProvider()
    return _provider


def set_ocr_provider(p: OCRProvider | None):  # for tests / swapping engines
    global _provider
    _provider = p
