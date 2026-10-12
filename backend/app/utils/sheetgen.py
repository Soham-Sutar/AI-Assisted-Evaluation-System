"""Synthetic 'handwriting-like' answer-sheet renderer used by tests and the demo-data script.

NOT real handwriting: glyphs are drawn from an italic font with per-character jitter (rotation, baseline wobble,
ink variation), paper noise, blur and optional page skew. It exercises the real CV/OCR pipeline end-to-end.
"""
from __future__ import annotations

import random
import textwrap

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_jittery(img: Image.Image, xy: tuple[int, int], text: str, font, rng: random.Random, ink=(25, 35, 110),
                  jitter: float = 1.0) -> int:
    """Draw text glyph-by-glyph with jitter. Returns the x after the last glyph."""
    x, y = xy
    for ch in text:
        if ch == " ":
            x += int(font.size * 0.32)
            continue
        bbox = font.getbbox(ch)
        gw, gh = max(bbox[2] + 6, 8), font.size + 16
        layer = Image.new("RGBA", (gw + 10, gh + 10), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        shade = tuple(max(0, min(255, c + rng.randint(-12, 12))) for c in ink)
        d.text((4, 4), ch, font=font, fill=shade + (255,))
        layer = layer.rotate(rng.uniform(-4, 4) * jitter, resample=Image.BICUBIC, expand=True)
        img.paste(layer, (x, y + int(rng.uniform(-2, 2) * jitter)), layer)
        x += int(font.getlength(ch)) + rng.randint(-1, 1)
    return x


def render_page(items: list[tuple], size=(1240, 1754), marker_fmt: str = "Q{n}", seed: int = 0, skew: float = 0.0,
                noise: bool = True, marker_x: int = 90, text_x: int = 200, font_size: int = 40,
                line_gap: int = 22, jitter: float = 1.0, top: int = 150) -> Image.Image:
    """items: ('marker', n) | ('text', str) | ('gap', px) | ('header', str).
    A marker is drawn in the left margin; the following 'text' line starts to its right on the same line."""
    rng = random.Random(seed)
    W, H = size
    img = Image.new("RGB", size, (250, 248, 242))
    f_text, f_mark, f_head = _font(font_size), _font(font_size + 6), _font(font_size - 6)
    y = top
    marker_end = 0
    for kind, val in items:
        if kind == "header":
            _draw_jittery(img, (text_x, 60), val, f_head, rng, ink=(60, 60, 60), jitter=0.3)
        elif kind == "gap":
            y += int(val)
        elif kind == "marker":
            marker_end = _draw_jittery(img, (marker_x, y), marker_fmt.format(n=val), f_mark, rng, jitter=jitter)
        elif kind == "text":
            max_chars = max(20, int((W - text_x - 100) / (font_size * 0.42)))
            for i, line in enumerate(textwrap.wrap(val, max_chars) or [""]):
                start = max(text_x, marker_end + 25) if (i == 0 and marker_end) else text_x
                _draw_jittery(img, (start, y), line, f_text, rng, jitter=jitter)
                y += font_size + line_gap
            marker_end = 0
    if noise:
        arr = np.array(img).astype(np.int16)
        nz = np.random.RandomState(seed).normal(0, 4, arr.shape)
        img = Image.fromarray(np.clip(arr + nz, 0, 255).astype(np.uint8))
    img = img.filter(ImageFilter.GaussianBlur(0.7))
    if skew:
        img = img.rotate(skew, resample=Image.BICUBIC, fillcolor=(250, 248, 242))
    return img
