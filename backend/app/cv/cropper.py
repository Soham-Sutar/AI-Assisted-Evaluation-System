"""Crop-region calculation, cropping, multi-page merging and saving of segmented answers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.cv.question_detector import QuestionMarker


@dataclass
class Region:
    question_number: int | None  # None => continuation of the previously open question
    y0: int
    y1: int
    marker: QuestionMarker | None = None

    @property
    def height(self) -> int:
        return self.y1 - self.y0


def calculate_crop_regions(markers: list[QuestionMarker], page_height: int, ink_bottom: int | None = None,
                           top_padding: int = 12, bottom_padding: int = 8, separator_padding: int = 6,
                           continuation_min_height: int = 40, allow_continuation: bool = True,
                           ink_top: int | None = None) -> list[Region]:
    """Guide section 18: start = marker top, end = next marker top (last: bottom of page content).

    `markers` must all belong to ONE page and be sorted by y. `ink_top` = first row containing ink (None = unknown). Bounds-checked against page_height.
    If content exists above the first marker it is returned as a continuation region (question_number=None).
    With no markers the whole inked page is a continuation region."""
    bottom_limit = page_height
    if ink_bottom is not None and ink_bottom > 0:
        bottom_limit = min(page_height, ink_bottom + bottom_padding + 1)
    regions: list[Region] = []
    if not markers:
        if allow_continuation and bottom_limit > continuation_min_height:
            regions.append(Region(None, 0, bottom_limit))
        return regions
    first_y = max(0, markers[0].y - top_padding)
    # A continuation exists only if there is real ink above the first marker (blank top margins are not content).
    ink_above = ink_top is None or ink_top < first_y - 4
    if allow_continuation and first_y >= continuation_min_height and ink_above:
        regions.append(Region(None, 0, max(1, markers[0].y - separator_padding)))
    for i, m in enumerate(markers):
        y0 = max(0, m.y - top_padding)
        if i < len(markers) - 1:
            y1 = markers[i + 1].y - separator_padding
        else:
            y1 = bottom_limit
        y1 = int(min(page_height, max(y1, m.y + m.height + 4)))  # never smaller than the marker line itself
        y0 = int(min(y0, y1 - 1))
        regions.append(Region(m.question_number, y0, y1, m))
    return regions


def crop_answer(img: np.ndarray, y0: int, y1: int) -> np.ndarray:
    """Full-width crop with bounds checking (full width keeps margins/context for the evaluator)."""
    h = img.shape[0]
    y0 = int(max(0, min(y0, h - 1)))
    y1 = int(max(y0 + 1, min(y1, h)))
    return img[y0:y1, :].copy()


def merge_multipage_answer(parts: list[np.ndarray], gap: int = 10) -> np.ndarray:
    """Stack crops (top-to-bottom, page order) into one image, white-padding to equal width with a thin
    grey separator so the faculty member can see where a page break occurred."""
    if len(parts) == 1:
        return parts[0]
    width = max(p.shape[1] for p in parts)
    out = []
    for i, p in enumerate(parts):
        if p.ndim == 2:
            p = cv2.cvtColor(p, cv2.COLOR_GRAY2BGR)
        if p.shape[1] < width:
            p = cv2.copyMakeBorder(p, 0, 0, 0, width - p.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
        out.append(p)
        if i < len(parts) - 1:
            sep = np.full((gap, width, 3), 255, np.uint8)
            sep[gap // 2, :] = (160, 160, 160)
            out.append(sep)
    return np.vstack(out)


def save_segment(img: np.ndarray, directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    ok = cv2.imwrite(str(path), img)
    if not ok:
        raise IOError(f"Could not write segment image {path}")
    return path
