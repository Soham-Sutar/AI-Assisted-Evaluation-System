"""Image preprocessing (OpenCV). The ORIGINAL file is never modified; callers save derived images separately.

Pipeline: load -> grayscale -> denoise -> CLAHE contrast -> binarize -> deskew.
Geometry convention: all coordinates elsewhere (markers, crops) are in the *deskewed* frame.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


def load_image(path: str | Path) -> np.ndarray:
    """Load as BGR uint8, honouring EXIF orientation (phone scans)."""
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
        arr = np.array(im)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def normalize_size(img: np.ndarray, max_side: int = 4000) -> np.ndarray:
    """Downscale only when excessively large (resize only when necessary)."""
    h, w = img.shape[:2]
    m = max(h, w)
    if m <= max_side:
        return img
    s = max_side / m
    return cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)


def to_grayscale(img: np.ndarray) -> np.ndarray:
    return img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def denoise(gray: np.ndarray) -> np.ndarray:
    return cv2.GaussianBlur(gray, (3, 3), 0)


def enhance_contrast(gray: np.ndarray) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)


def threshold(gray: np.ndarray) -> np.ndarray:
    """Binary image, ink = 255 (inverted) is produced by `ink_mask`; this returns ink black on white."""
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
    return bw


def ink_mask(gray: np.ndarray) -> np.ndarray:
    """Ink pixels = 255. Uses Otsu with a guard for near-uniform (blank) pages."""
    g = denoise(gray)
    if g.std() < 6:  # essentially blank page
        return np.zeros_like(g)
    _, m = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return m


def estimate_skew(gray: np.ndarray, max_angle: float = 5.0) -> float:
    """Projection-profile skew estimate: the angle whose row-sum profile has maximum variance
    (text lines align with rows). Coarse (0.5 deg) then fine (0.1 deg) search on a downscaled copy."""
    h, w = gray.shape[:2]
    s = 700 / max(w, 1)
    small = cv2.resize(gray, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else gray
    m = ink_mask(small)
    if m.sum() < 255 * 50:
        return 0.0
    ys, xs = np.nonzero(m)
    pts = np.stack([xs, ys], 1).astype(np.float32)
    c = pts.mean(0)

    def score(angle: float) -> float:
        r = np.deg2rad(angle)
        y = (pts[:, 0] - c[0]) * np.sin(r) + (pts[:, 1] - c[1]) * np.cos(r)
        hist, _ = np.histogram(y, bins=max(int(small.shape[0] / 2), 50))
        return float(np.var(hist))

    coarse = max(np.arange(-max_angle, max_angle + 0.01, 0.5), key=score)
    fine = max(np.arange(coarse - 0.5, coarse + 0.51, 0.1), key=score)
    return round(float(fine), 2)


def rotate(img: np.ndarray, angle: float) -> np.ndarray:
    if abs(angle) < 0.2:
        return img
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    border = (255, 255, 255) if img.ndim == 3 else 255
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=border)


def deskew(img: np.ndarray) -> tuple[np.ndarray, float]:
    """Returns (deskewed image, angle applied). Angle is in degrees as given to cv2.getRotationMatrix2D."""
    angle = estimate_skew(to_grayscale(img))
    # Projection-profile angle is the skew of the text; rotating by the same signed angle levels it.
    return rotate(img, angle), angle


@dataclass
class Preprocessed:
    color: np.ndarray       # deskewed colour page (used for crops shown to faculty)
    gray_enhanced: np.ndarray  # deskewed, denoised, CLAHE grayscale (fed to OCR)
    binary: np.ndarray      # deskewed binarised page (saved as the "processed" image)
    angle: float


def preprocess_for_ocr(img: np.ndarray, angle: float | None = None) -> Preprocessed:
    img = normalize_size(img)
    if angle is None:
        color, angle = deskew(img)
    else:
        color = rotate(img, angle)
    gray = to_grayscale(color)
    enhanced = enhance_contrast(denoise(gray))
    return Preprocessed(color=color, gray_enhanced=enhanced, binary=threshold(enhanced), angle=angle)


def ink_ratio(gray_or_color: np.ndarray) -> float:
    g = to_grayscale(gray_or_color)
    m = ink_mask(g)
    return float((m > 0).mean())


def last_ink_row(gray: np.ndarray, min_row_ink: int = 2) -> int:
    """Index of the last row containing ink (0 if page is blank)."""
    m = ink_mask(gray)
    rows = np.nonzero((m > 0).sum(axis=1) >= min_row_ink)[0]
    return int(rows[-1]) if len(rows) else 0


def first_ink_row(gray: np.ndarray, min_row_ink: int = 2) -> int:
    """Index of the first row containing ink (0 if page is blank)."""
    m = ink_mask(gray)
    rows = np.nonzero((m > 0).sum(axis=1) >= min_row_ink)[0]
    return int(rows[0]) if len(rows) else 0
