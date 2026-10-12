"""Question-marker detection from OCR word data.

Markers recognised: Q1, Q.1, Q 1, Q-1, 1., 1), 1 ), Question 1, QUESTION 1, Question 1:
Contextual validation (guide section 17): left margin, OCR confidence, number must belong to the
exam's configured question set. A longest-increasing-subsequence pass then removes stray numbered
sub-points inside answers (e.g. "1)" inside the answer to Q2).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

import numpy as np

from app.services.ocr_service import OCRProvider, OCRWord

PREFIXED = "prefixed"  # Q1 / Question 1
BARE = "bare"          # 1. / 1)

_RE_QUESTION = re.compile(r"^(?:QUESTION|QUES|QUEST|QN)[\s.\-_:]*([0-9]{1,2}|[IL|!\]\[/]{1,2})(?![A-Z])")
_RE_Q = re.compile(r"^Q[\s.\-_:]*([0-9]{1,2}|[ILO|SB!\]\[/]{1,2})(?![A-Z])")
_RE_BARE = re.compile(r"^([0-9]{1,2})[.)]")
_RE_BARE_CONFUSED = re.compile(r"^([IL|])[.)]$")

# Handwriting OCR confusions in the digit position following a Q prefix.
_DIGIT_CONFUSION = str.maketrans({"I": "1", "L": "1", "|": "1", "!": "1", "]": "1", "[": "1", "/": "1",
                                  "O": "0", "S": "5", "B": "8", "Z": "2"})


@dataclass
class QuestionMarker:
    question_number: int
    x: int
    y: int
    width: int
    height: int
    confidence: float  # 0-1
    text: str = ""
    page_number: int = 1
    style: str = PREFIXED
    source: str = "full"  # full | blob (margin blob re-read)
    ocr_confidence: float = 0.0  # raw OCR confidence of the marker token(s), 0-1

    def to_dict(self) -> dict:
        d = asdict(self)
        d["confidence"] = round(self.confidence, 3)
        return d


@dataclass
class DetectionResult:
    markers: list[QuestionMarker] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)  # {marker..., reason}


def normalize_ocr_token(raw: str) -> str:
    """'Q. 1' -> 'Q1', 'Q-1' -> 'Q1', 'Question 1:' -> 'QUESTION1:' (upper-cased, spaces/odd dashes removed)."""
    s = (raw or "").strip().replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    s = re.sub(r"^[\[\(\{]+", "", s)
    s = re.sub(r"\s+", "", s).upper()
    # 'Q.1' / 'Q-1' / 'Q:1' / 'Q_1' -> 'Q1'
    s = re.sub(r"^Q[.\-_:]+(?=[0-9ILO|SBZ!\]\[/])", "Q", s)
    return s


def detect_question_marker(tokens: list[str]) -> tuple[int, str, int] | None:
    """Try to read a marker at the start of a line from its first tokens.
    Returns (question_number, style, tokens_consumed) or None."""
    for k in range(1, min(3, len(tokens)) + 1):
        norm = normalize_ocr_token("".join(tokens[:k]))
        if not norm:
            continue
        m = _RE_QUESTION.match(norm)
        if m:
            digits = m.group(1).translate(_DIGIT_CONFUSION)
            if digits.isdigit() and 0 < int(digits) < 100:
                return int(digits), PREFIXED, k
        m = _RE_Q.match(norm)
        if m:
            digits = m.group(1).translate(_DIGIT_CONFUSION)
            if digits.isdigit() and 0 < int(digits) < 100:
                return int(digits), PREFIXED, k
        m = _RE_BARE.match(norm)
        if m and 0 < int(m.group(1)) < 100:
            return int(m.group(1)), BARE, k
        if k == 1:
            m = _RE_BARE_CONFUSED.match(norm)
            if m:
                return 1, BARE, k
    return None


def extract_ocr_data(gray: np.ndarray, provider: OCRProvider, left_margin_frac: float = 0.35) -> list[OCRWord]:
    """OCR pass 1: whole page (psm 6). OCR pass 2 ('blob re-read'): isolated ink blobs in the left margin that no
    confident word covers (typical for short handwritten markers like '1.' that a full-page pass misreads)
    are cropped, enlarged and re-read individually (psm 8, marker-character whitelist).
    Coordinates are returned in the input image's frame (upscaled passes are mapped back)."""
    h, w = gray.shape[:2]
    scale = 2.0 if w < 1400 else 1.0
    full = provider.extract(_resize(gray, scale), psm=6)
    words = [_rescale(wd, scale, "full") for wd in full.words]
    words += recover_margin_blobs(gray, words, provider, min(left_margin_frac, 0.30))
    return words


def recover_margin_blobs(gray: np.ndarray, words: list[OCRWord], provider: OCRProvider,
                         zone_frac: float = 0.30, max_blobs: int = 40) -> list[OCRWord]:
    import cv2
    from app.cv.preprocessing import ink_mask

    h, w = gray.shape[:2]
    zone_w = int(w * zone_frac)
    mask = ink_mask(gray)[:, :zone_w]
    if mask.sum() == 0:
        return []
    dil = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (21, 9)))
    n, _, stats, _ = cv2.connectedComponentsWithStats(dil)
    confident = [wd for wd in words if wd.conf >= 60]
    out: list[OCRWord] = []
    blobs = sorted(range(1, n), key=lambda i: stats[i][1])[:max_blobs]
    for i in blobs:
        x, y, bw, bh, area = stats[i]
        if bh < 14 or bh > 140 or bw > 260 or bw < 8:
            continue
        if x + bw >= zone_w - 2:  # touches the zone edge => it is the start of a text line, not an isolated marker
            continue
        if any(_overlap(x, y, bw, bh, c.x, c.y, c.w, c.h) for c in confident):
            continue
        pad = 14
        x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(w, x + bw + pad), min(h, y + bh + pad)
        crop = gray[y0:y1, x0:x1]
        s = 90.0 / max(crop.shape[0], 1)
        crop = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
        # Experiment-driven (see docs/segmentation.md): Otsu-binarised + slightly thickened ink, read as ONE text
        # line (psm 7), is far more reliable for isolated markers than psm 8 on the grey crop.
        _, crop = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        crop = cv2.erode(crop, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
        crop = cv2.copyMakeBorder(crop, 25, 25, 25, 25, cv2.BORDER_CONSTANT, value=255)
        res = provider.extract(crop, psm=7, whitelist="Qq0123456789.:)-lI|")
        if not res.words:
            continue
        text = "".join(wd.text for wd in res.words)
        conf = float(np.mean([wd.conf for wd in res.words]))
        wd = OCRWord(text, conf, int(x), int(y), int(bw), int(bh), 2000 + int(i), 0, 0)
        wd.source = "blob"  # type: ignore[attr-defined]
        out.append(wd)
    return out


def _overlap(ax, ay, aw, ah, bx, by, bw, bh) -> bool:
    ix = min(ax + aw, bx + bw) - max(ax, bx)
    iy = min(ay + ah, by + bh) - max(ay, by)
    return ix > 0 and iy > 0


def _resize(img: np.ndarray, scale: float) -> np.ndarray:
    if scale == 1.0:
        return img
    import cv2
    return cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def _rescale(w: OCRWord, scale: float, source: str) -> OCRWord:
    nw = OCRWord(w.text, w.conf, int(w.x / scale), int(w.y / scale), int(w.w / scale), int(w.h / scale),
                 w.block, w.par, w.line)
    nw.source = source  # type: ignore[attr-defined]
    return nw


def _group_lines(words: list[OCRWord]) -> list[list[OCRWord]]:
    groups: dict[tuple, list[OCRWord]] = {}
    for w in words:
        groups.setdefault((getattr(w, "source", "full"), w.block, w.par, w.line), []).append(w)
    lines = [sorted(g, key=lambda x: x.x) for g in groups.values()]
    return sorted(lines, key=lambda g: (g[0].y, g[0].x))


def validate_marker(marker: QuestionMarker, page_width: int, configured: set[int], min_conf: float,
                    left_margin_frac: float) -> str | None:
    """Return a rejection reason, or None if the marker is acceptable."""
    if configured and marker.question_number not in configured:
        return f"question {marker.question_number} not in configured set"
    if marker.x > page_width * left_margin_frac:
        return "not in left margin"
    if marker.ocr_confidence * 100 < min_conf:
        return "low OCR confidence"
    return None


def detect_question_markers(words: list[OCRWord], page_width: int, page_height: int, configured: set[int],
                            page_number: int = 1, min_conf: float = 30.0,
                            left_margin_frac: float = 0.35) -> DetectionResult:
    """Find marker candidates on one page. Does NOT yet resolve ordering/duplicates across pages
    (see `select_marker_sequence`)."""
    res = DetectionResult()
    cands: list[QuestionMarker] = []
    for line in _group_lines(words):
        hit = detect_question_marker([w.text for w in line[:3]])
        if not hit:
            continue
        num, style, used = hit
        used_words = line[:used]
        x = min(w.x for w in used_words)
        y = min(w.y for w in used_words)
        x2 = max(w.x + w.w for w in used_words)
        y2 = max(w.y + w.h for w in used_words)
        ocr_conf = float(np.mean([w.conf for w in used_words])) / 100.0
        pos = float(np.clip(1.0 - x / max(page_width * left_margin_frac, 1), 0.0, 1.0))
        known = 1.0 if (not configured or num in configured) else 0.0
        conf = 0.65 * ocr_conf + 0.20 * (0.5 + 0.5 * pos) + 0.15 * known
        m = QuestionMarker(num, x, y, x2 - x, y2 - y, round(min(conf, 1.0), 3), " ".join(w.text for w in used_words),
                           page_number, style, getattr(used_words[0], "source", "full"), round(ocr_conf, 3))
        reason = validate_marker(m, page_width, configured, min_conf, left_margin_frac)
        if reason:
            res.rejected.append({**m.to_dict(), "reason": reason})
        else:
            cands.append(m)
    # De-duplicate the two OCR passes: same number and vertically close -> keep higher confidence.
    cands.sort(key=lambda m: (m.y, -m.confidence))
    kept: list[QuestionMarker] = []
    for m in cands:
        dup = next((k for k in kept if k.question_number == m.question_number
                    and abs(k.y - m.y) <= max(k.height, m.height, 20) * 1.5), None)
        if dup is None:
            kept.append(m)
        elif m.confidence > dup.confidence:
            kept[kept.index(dup)] = m
        else:
            res.rejected.append({**m.to_dict(), "reason": "duplicate of nearby marker"})
    res.markers = sort_markers(kept)
    return res


def sort_markers(markers: list[QuestionMarker]) -> list[QuestionMarker]:
    return sorted(markers, key=lambda m: (m.page_number, m.y, m.x))


def select_marker_sequence(markers: list[QuestionMarker]) -> tuple[list[QuestionMarker], list[dict]]:
    """Resolve candidates across all pages of one answer sheet.

    1. If prefixed markers (Q1/Question 1) exist, drop bare ones ("1.") - a student's numbered sub-points
       must not be mistaken for questions.
    2. Keep the maximum-confidence-weight subsequence in reading order (page, y) whose question numbers are
       strictly increasing. Everything else is rejected with a reason (out of order / duplicate number).
    """
    rejected: list[dict] = []
    ms = sort_markers(markers)
    if any(m.style == PREFIXED for m in ms):
        for m in ms:
            if m.style == BARE:
                rejected.append({**m.to_dict(), "reason": "bare number ignored (prefixed markers present)"})
        ms = [m for m in ms if m.style == PREFIXED]
    n = len(ms)
    if n == 0:
        return [], rejected
    best = [m.confidence for m in ms]
    prev = [-1] * n
    for i in range(n):
        for j in range(i):
            if ms[j].question_number < ms[i].question_number and best[j] + ms[i].confidence > best[i]:
                best[i] = best[j] + ms[i].confidence
                prev[i] = j
    end = int(np.argmax(best))
    chosen_idx = []
    while end != -1:
        chosen_idx.append(end)
        end = prev[end]
    chosen_idx.reverse()
    chosen = [ms[i] for i in chosen_idx]
    for i, m in enumerate(ms):
        if i not in chosen_idx:
            rejected.append({**m.to_dict(), "reason": "out of order or duplicate question number"})
    return chosen, rejected
