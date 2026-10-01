import io
import os
import tempfile
import pytest
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from app.models.question import Question
from app.models.answer import SegmentationStatus
from app.services.storage import (
    validate_file_upload,
    get_answer_sheet_dirs,
    save_original_file,
    verify_safe_path,
    get_base_storage_dir,
)
from app.services.image_processing import (
    load_image_from_bytes,
    load_image_from_path,
    save_image,
    to_grayscale,
    enhance_contrast,
    denoise_image,
    estimate_skew_angle,
    rotate_image,
    preprocess_page,
    crop_image_region,
    ImageProcessingError,
)
from app.services.ocr import extract_ocr_data
from app.services.segmentation import (
    match_question_header,
    detect_question_markers_on_page,
    segment_page_questions,
    segment_answer_sheet,
)
from fastapi import HTTPException


# ==============================================================================
# Helper to create synthetic test images with text
# ==============================================================================
def create_test_image_with_text(lines: list[str], width: int = 800, height: int = 1000) -> Image.Image:
    """Create a high-contrast black-on-white image with text lines."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    y = 50
    for line in lines:
        draw.text((50, y), line, fill=(0, 0, 0))
        y += 100
    return img


# ==============================================================================
# 1. STORAGE SERVICE TESTS
# ==============================================================================
def test_validate_file_upload_allowed_types():
    assert validate_file_upload("sheet.png", "image/png", 1000) == ".png"
    assert validate_file_upload("sheet.jpg", "image/jpeg", 1000) == ".jpg"
    assert validate_file_upload("sheet.jpeg", "image/jpeg", 1000) == ".jpeg"
    assert validate_file_upload("sheet.pdf", "application/pdf", 1000) == ".pdf"


def test_validate_file_upload_unsupported_extension():
    with pytest.raises(HTTPException) as exc_info:
        validate_file_upload("sheet.exe", "application/octet-stream", 1000)
    assert exc_info.value.status_code == 400
    assert "Unsupported file format" in exc_info.value.detail


def test_validate_file_upload_unsupported_mime():
    with pytest.raises(HTTPException) as exc_info:
        validate_file_upload("sheet.png", "text/plain", 1000)
    assert exc_info.value.status_code == 400


def test_validate_file_upload_size_limit():
    with pytest.raises(HTTPException) as exc_info:
        # 25 MB exceeds 20MB default
        validate_file_upload("sheet.png", "image/png", 25 * 1024 * 1024)
    assert exc_info.value.status_code == 413


def test_get_answer_sheet_dirs_and_save_original(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.STORAGE_PATH", str(tmp_path))
    sheet_id = "test-sheet-123"
    dirs = get_answer_sheet_dirs(sheet_id)

    assert dirs["original"].exists()
    assert dirs["processed"].exists()
    assert dirs["crops"].exists()

    content = b"fake-image-bytes"
    saved_path = save_original_file(sheet_id, content, ".png")
    assert os.path.exists(saved_path)
    with open(saved_path, "rb") as f:
        assert f.read() == content


def test_path_traversal_protection(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.STORAGE_PATH", str(tmp_path))
    with pytest.raises(ValueError):
        verify_safe_path("../../../etc/passwd")


# ==============================================================================
# 2. IMAGE PREPROCESSING TESTS
# ==============================================================================
def test_image_loading_and_saving(tmp_path):
    img = create_test_image_with_text(["Test Header"])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    cv_img = load_image_from_bytes(img_bytes)
    assert cv_img is not None
    assert isinstance(cv_img, np.ndarray)
    assert len(cv_img.shape) == 3

    temp_save = str(tmp_path / "saved.png")
    saved_res = save_image(cv_img, temp_save)
    assert os.path.exists(saved_res)

    loaded_back = load_image_from_path(temp_save)
    assert loaded_back.shape == cv_img.shape


def test_invalid_image_loading_raises():
    with pytest.raises(ImageProcessingError):
        load_image_from_bytes(b"invalid corrupt bytes not an image")


def test_preprocessing_pipeline():
    img = create_test_image_with_text(["Q.1 Database Systems", "Answer to Q1 here."])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    cv_img = load_image_from_bytes(buf.getvalue())

    orig_copy = cv_img.copy()
    processed = preprocess_page(cv_img)

    assert isinstance(processed, np.ndarray)
    assert len(processed.shape) == 2  # Grayscale
    # Verify original cv_img is untouched
    assert np.array_equal(cv_img, orig_copy)


def test_crop_image_region():
    img = np.zeros((1000, 800, 3), dtype=np.uint8)
    # Put white square at y=200..400
    img[200:400, 100:500] = 255

    crop = crop_image_region(img, top=200, bottom=400, left=100, right=500, padding_y=0, padding_x=0)
    assert crop.shape == (200, 400, 3)


# ==============================================================================
# 3. OCR TESTS
# ==============================================================================
def test_ocr_extract_data_on_synthetic_image():
    img = create_test_image_with_text(["Q.1 Explain ACID Properties", "Atomicity, Consistency, Isolation, Durability"])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    cv_img = load_image_from_bytes(buf.getvalue())

    res = extract_ocr_data(cv_img)
    assert res["success"] is True
    assert res["error"] is None
    assert isinstance(res["text"], str)
    assert "ACID" in res["text"] or "Properties" in res["text"] or len(res["text"]) > 0
    if res["confidence"] is not None:
        assert 0.0 <= res["confidence"] <= 100.0
    assert isinstance(res["word_boxes"], list)


def test_ocr_on_blank_image():
    blank = np.full((500, 500), 255, dtype=np.uint8)
    res = extract_ocr_data(blank)
    assert res["success"] is True
    assert res["text"] == ""
    assert res["word_boxes"] == []


# ==============================================================================
# 4. QUESTION SEGMENTATION TESTS
# ==============================================================================
def test_match_question_header_patterns():
    assert match_question_header("Q.1") == 1
    assert match_question_header("Q1") == 1
    assert match_question_header("Q-2") == 2
    assert match_question_header("Question 3") == 3
    assert match_question_header("Ans 4") == 4
    assert match_question_header("1.") == 1
    assert match_question_header("(2)") == 2
    assert match_question_header("[3]") == 3
    assert match_question_header("Random handwritten text") is None


def test_detect_question_markers_on_page():
    word_boxes = [
        {"text": "Q.1", "top": 100, "left": 50, "height": 30, "conf": 90.0},
        {"text": "What", "top": 100, "left": 100, "height": 30, "conf": 85.0},
        {"text": "is", "top": 100, "left": 160, "height": 30, "conf": 88.0},
        {"text": "Q.2", "top": 450, "left": 50, "height": 30, "conf": 92.0},
        {"text": "Explain", "top": 450, "left": 100, "height": 30, "conf": 87.0},
    ]
    markers = detect_question_markers_on_page(word_boxes, expected_q_nums=[1, 2])
    assert len(markers) == 2
    assert markers[0]["question_number"] == 1
    assert markers[0]["top"] == 100
    assert markers[1]["question_number"] == 2
    assert markers[1]["top"] == 450


def test_segment_answer_sheet_generates_crops(tmp_path):
    crops_dir = tmp_path / "crops"
    
    # Create fake questions
    q1 = Question(id="q1-id", examination_id="exam-id", question_number=1, question_text="Q1 text", max_marks=5.0)
    q2 = Question(id="q2-id", examination_id="exam-id", question_number=2, question_text="Q2 text", max_marks=5.0)
    
    page_img = np.full((1000, 800, 3), 255, dtype=np.uint8)
    word_boxes = [
        {"text": "Q.1", "top": 100, "left": 50, "height": 30, "conf": 90.0},
        {"text": "Answer", "top": 150, "left": 50, "height": 30, "conf": 85.0},
        {"text": "Q.2", "top": 500, "left": 50, "height": 30, "conf": 92.0},
        {"text": "Answer2", "top": 550, "left": 50, "height": 30, "conf": 88.0},
    ]

    pages_data = [{
        "page_id": "page-1-id",
        "page_number": 1,
        "image": page_img,
        "processed_image": page_img,
        "word_boxes": word_boxes,
        "ocr_text": "Q.1 Answer Q.2 Answer2",
        "ocr_confidence": 88.0,
    }]

    answers, requires_review = segment_answer_sheet(
        pages_data=pages_data,
        expected_questions=[q1, q2],
        crops_dir=crops_dir,
    )

    assert len(answers) == 2
    assert answers[0]["question_id"] == "q1-id"
    assert answers[0]["status"] == SegmentationStatus.DETECTED
    assert os.path.exists(answers[0]["crop_image_path"])

    assert answers[1]["question_id"] == "q2-id"
    assert answers[1]["status"] == SegmentationStatus.DETECTED
    assert os.path.exists(answers[1]["crop_image_path"])
    assert requires_review is False


def test_segment_answer_sheet_missing_question_requires_review(tmp_path):
    crops_dir = tmp_path / "crops"
    q1 = Question(id="q1-id", examination_id="exam-id", question_number=1, question_text="Q1 text", max_marks=5.0)
    q2 = Question(id="q2-id", examination_id="exam-id", question_number=2, question_text="Q2 text", max_marks=5.0)

    page_img = np.full((1000, 800, 3), 255, dtype=np.uint8)
    # Only Q.1 is present on page
    word_boxes = [
        {"text": "Q.1", "top": 100, "left": 50, "height": 30, "conf": 90.0},
        {"text": "Answer", "top": 150, "left": 50, "height": 30, "conf": 85.0},
    ]

    pages_data = [{
        "page_id": "page-1-id",
        "page_number": 1,
        "image": page_img,
        "processed_image": page_img,
        "word_boxes": word_boxes,
        "ocr_text": "Q.1 Answer",
        "ocr_confidence": 87.5,
    }]

    answers, requires_review = segment_answer_sheet(
        pages_data=pages_data,
        expected_questions=[q1, q2],
        crops_dir=crops_dir,
    )

    assert len(answers) == 2
    assert requires_review is True
    q2_ans = next(a for a in answers if a["question_id"] == "q2-id")
    assert q2_ans["status"] == SegmentationStatus.NEEDS_REVIEW
