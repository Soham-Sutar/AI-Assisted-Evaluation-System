import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.models.answer import SegmentationStatus
from app.models.question import Question
from app.services.image_processing import crop_image_region, save_image
from app.services.ocr import extract_ocr_data

# Patterns to identify question headers in OCR text
QUESTION_HEADER_PATTERNS = [
    # Q.1, Q1, Q-1, Q 1, Q. 1, Question 1, Question. 1, Question-1
    re.compile(r"^(?:q|quest|question|ans|answer)[\.\s\:\-]*(\d+)", re.IGNORECASE),
    # 1., 1), (1), [1] at start of line
    re.compile(r"^[\(\[\s]*(\d+)[\.\)\:\-\]]", re.IGNORECASE),
]


def match_question_header(text: str) -> Optional[int]:
    """
    Check if a text token or line matches a question header pattern.
    Returns the integer question number if matched, None otherwise.
    """
    clean = text.strip()
    if not clean:
        return None

    for pat in QUESTION_HEADER_PATTERNS:
        m = pat.match(clean)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


def detect_question_markers_on_page(
    word_boxes: List[Dict[str, Any]],
    expected_q_nums: List[int],
) -> List[Dict[str, Any]]:
    """
    Find vertical positions and bounding boxes of question markers on a page
    using OCR word bounding boxes.
    """
    markers: List[Dict[str, Any]] = []
    seen_q_nums = set()

    # Step 1: Check single word tokens
    for box in word_boxes:
        word = box["text"].strip()
        q_num = match_question_header(word)
        if q_num is not None and q_num in expected_q_nums and q_num not in seen_q_nums:
            markers.append({
                "question_number": q_num,
                "top": box["top"],
                "left": box["left"],
                "height": box["height"],
                "conf": box.get("conf", 80.0),
                "pattern": "single_word",
            })
            seen_q_nums.add(q_num)

    # Step 2: Check adjacent 2-word combinations (e.g. "Q." followed by "1" or "Question" followed by "1")
    if len(word_boxes) > 1:
        for i in range(len(word_boxes) - 1):
            w1 = word_boxes[i]["text"].strip()
            w2 = word_boxes[i + 1]["text"].strip()
            combined = f"{w1} {w2}"
            q_num = match_question_header(combined)
            if q_num is not None and q_num in expected_q_nums and q_num not in seen_q_nums:
                top_pos = min(word_boxes[i]["top"], word_boxes[i + 1]["top"])
                left_pos = min(word_boxes[i]["left"], word_boxes[i + 1]["left"])
                markers.append({
                    "question_number": q_num,
                    "top": top_pos,
                    "left": left_pos,
                    "height": max(word_boxes[i]["height"], word_boxes[i + 1]["height"]),
                    "conf": min(word_boxes[i].get("conf", 80.0), word_boxes[i + 1].get("conf", 80.0)),
                    "pattern": "two_word",
                })
                seen_q_nums.add(q_num)

    # Sort markers vertically by Y-coordinate
    markers.sort(key=lambda x: x["top"])
    return markers


def segment_page_questions(
    page_image: np.ndarray,
    page_id: str,
    word_boxes: List[Dict[str, Any]],
    expected_questions: List[Question],
    crops_dir: Path,
) -> List[Dict[str, Any]]:
    """
    Perform question segmentation on a single page image.
    Generates crop images on disk and extracts question-specific text and confidence.
    """
    h, w = page_image.shape[:2]
    expected_q_map = {q.question_number: q for q in expected_questions}
    expected_q_nums = sorted(expected_q_map.keys())

    detected_markers = detect_question_markers_on_page(word_boxes, expected_q_nums)
    segments: List[Dict[str, Any]] = []

    if detected_markers:
        for idx, marker in enumerate(detected_markers):
            q_num = marker["question_number"]
            q_model = expected_q_map.get(q_num)
            if not q_model:
                continue

            top_y = marker["top"]
            # Bottom boundary is the top of next question marker or end of page
            if idx + 1 < len(detected_markers):
                bottom_y = detected_markers[idx + 1]["top"]
            else:
                bottom_y = h

            # Crop region
            crop_img = crop_image_region(page_image, top=top_y, bottom=bottom_y, left=0, right=w)
            crop_filename = f"q{q_num}_{uuid.uuid4().hex[:8]}.png"
            crop_path = str((crops_dir / crop_filename).resolve())
            save_image(crop_img, crop_path)

            # Filter word boxes falling within [top_y, bottom_y]
            region_words = [
                b for b in word_boxes
                if top_y - 20 <= b["top"] <= bottom_y + 20 and b["text"].strip()
            ]
            region_text = " ".join(b["text"].strip() for b in region_words)
            region_confs = [b["conf"] for b in region_words if b.get("conf", -1) >= 0]
            avg_ocr_conf = round(float(np.mean(region_confs)), 2) if region_confs else None

            # Segmentation confidence based on marker detection quality
            marker_conf = marker.get("conf", 80.0)
            seg_conf = round(min(1.0, max(0.1, (marker_conf / 100.0) * 0.95)), 2)

            segments.append({
                "question_id": q_model.id,
                "question_number": q_num,
                "answer_page_id": page_id,
                "crop_image_path": crop_path,
                "ocr_text": region_text,
                "ocr_confidence": avg_ocr_conf,
                "segmentation_confidence": seg_conf,
                "status": SegmentationStatus.DETECTED if seg_conf >= 0.6 else SegmentationStatus.NEEDS_REVIEW,
            })

    return segments


def segment_answer_sheet(
    pages_data: List[Dict[str, Any]],
    expected_questions: List[Question],
    crops_dir: Path,
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Segment all pages of an answer sheet across all expected questions.
    Returns:
    - answers: list of answer record dicts for all expected questions
    - requires_review: bool indicating if any question was missed or low-confidence
    """
    crops_dir.mkdir(parents=True, exist_ok=True)
    all_segments: List[Dict[str, Any]] = []
    found_question_ids = set()

    # Segment each page
    for page_info in pages_data:
        page_img = page_info["image"]
        page_id = page_info["page_id"]
        word_boxes = page_info.get("word_boxes", [])

        page_segments = segment_page_questions(
            page_image=page_img,
            page_id=page_id,
            word_boxes=word_boxes,
            expected_questions=expected_questions,
            crops_dir=crops_dir,
        )
        for seg in page_segments:
            if seg["question_id"] not in found_question_ids:
                all_segments.append(seg)
                found_question_ids.add(seg["question_id"])

    # Check for missing expected questions
    requires_review = False
    for q in expected_questions:
        if q.id not in found_question_ids:
            requires_review = True
            # Create a placeholder answer marked for manual review
            # If there is at least one page, link to page 1
            first_page_id = pages_data[0]["page_id"] if pages_data else None
            
            # If there is only 1 question in exam and 1 page but no explicit marker, assign full page
            if len(expected_questions) == 1 and len(pages_data) >= 1:
                p_img = pages_data[0]["image"]
                crop_fn = f"q{q.question_number}_{uuid.uuid4().hex[:8]}.png"
                c_path = str((crops_dir / crop_fn).resolve())
                save_image(p_img, c_path)
                p_text = pages_data[0].get("ocr_text", "")
                p_conf = pages_data[0].get("ocr_confidence")
                all_segments.append({
                    "question_id": q.id,
                    "question_number": q.question_number,
                    "answer_page_id": first_page_id,
                    "crop_image_path": c_path,
                    "ocr_text": p_text,
                    "ocr_confidence": p_conf,
                    "segmentation_confidence": 0.60,
                    "status": SegmentationStatus.NEEDS_REVIEW,
                })
            else:
                all_segments.append({
                    "question_id": q.id,
                    "question_number": q.question_number,
                    "answer_page_id": first_page_id,
                    "crop_image_path": None,
                    "ocr_text": None,
                    "ocr_confidence": None,
                    "segmentation_confidence": None,
                    "status": SegmentationStatus.NEEDS_REVIEW,
                })

    for seg in all_segments:
        if seg["status"] == SegmentationStatus.NEEDS_REVIEW:
            requires_review = True

    return all_segments, requires_review
