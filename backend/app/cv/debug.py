"""Debug overlays: red boxes at detected markers, green crop boundaries, orange for rejected candidates."""
import cv2
import numpy as np


def draw_debug_page(img: np.ndarray, markers, regions, rejected=None) -> np.ndarray:
    out = img.copy() if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    h, w = out.shape[:2]
    for r in regions:
        cv2.line(out, (0, r.y0), (w, r.y0), (0, 160, 0), 2)
        cv2.line(out, (0, r.y1 - 1), (w, r.y1 - 1), (0, 160, 0), 1)
        label = f"Q{r.question_number}" if r.question_number is not None else "continuation"
        cv2.putText(out, label, (w - 170, r.y0 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 140, 0), 2)
    for m in markers:
        cv2.rectangle(out, (m.x - 4, m.y - 4), (m.x + m.width + 4, m.y + m.height + 4), (0, 0, 255), 2)
        cv2.putText(out, f"Q{m.question_number} {m.confidence:.2f}", (m.x, max(12, m.y - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
    for m in rejected or []:
        cv2.rectangle(out, (m["x"] - 3, m["y"] - 3), (m["x"] + m["width"] + 3, m["y"] + m["height"] + 3),
                      (0, 140, 255), 1)
    return out
