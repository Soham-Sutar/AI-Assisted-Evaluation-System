import io
import logging
import uuid
from pathlib import Path
from typing import List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from PIL import Image

from app.models.answer_sheet import AnswerSheet, ProcessingStatus
from app.models.answer_page import AnswerPage
from app.models.answer import Answer, SegmentationStatus
from app.models.examination import Examination
from app.models.question import Question
from app.services.storage import get_answer_sheet_dirs, save_original_file
from app.services.image_processing import (
    load_image_from_bytes,
    load_image_from_path,
    preprocess_page,
    save_image,
)
from app.services.ocr import extract_ocr_data
from app.services.segmentation import segment_answer_sheet

logger = logging.getLogger("evalai.processor")


def extract_pages_from_file(
    file_bytes: bytes,
    extension: str,
    original_dir: Path,
) -> List[Tuple[str, Image.Image]]:
    """
    Extract individual page PIL images from uploaded file (PDF, PNG, JPG).
    Saves each original page image into the original_dir.
    Returns list of (page_image_path, pil_image).
    """
    pages: List[Tuple[str, Image.Image]] = []
    ext = extension.lower()

    if ext == ".pdf":
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(file_bytes)
            for i, page in enumerate(pdf):
                # Render at 2x scale (~144 DPI) for clear text
                pil_image = page.render(scale=2.0).to_pil()
                page_filename = f"page_{i + 1}.png"
                page_path = str((original_dir / page_filename).resolve())
                pil_image.save(page_path, format="PNG")
                pages.append((page_path, pil_image))
        except Exception as e:
            logger.error(f"PDF extraction failed with pypdfium2: {e}")
            raise ValueError(f"Failed to process PDF answer sheet: {str(e)}") from e
    else:
        try:
            pil_image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            page_filename = "page_1.png"
            page_path = str((original_dir / page_filename).resolve())
            pil_image.save(page_path, format="PNG")
            pages.append((page_path, pil_image))
        except Exception as e:
            logger.error(f"Image loading failed: {e}")
            raise ValueError(f"Failed to process image answer sheet: {str(e)}") from e

    return pages


def process_answer_sheet_pipeline(
    db: Session,
    answer_sheet_id: str,
    file_bytes: bytes,
    extension: str,
) -> AnswerSheet:
    """
    Execute full ingestion, preprocessing, OCR, segmentation, and persistence pipeline.
    """
    # Fetch AnswerSheet record
    stmt = select(AnswerSheet).where(AnswerSheet.id == answer_sheet_id)
    answer_sheet = db.scalars(stmt).first()
    if not answer_sheet:
        raise ValueError(f"Answer sheet with ID '{answer_sheet_id}' not found")

    # Set processing status to PROCESSING
    answer_sheet.processing_status = ProcessingStatus.PROCESSING
    answer_sheet.error_message = None
    db.commit()

    try:
        dirs = get_answer_sheet_dirs(answer_sheet_id)

        # 1. Fetch Examination and its questions
        exam_stmt = select(Examination).where(Examination.id == answer_sheet.examination_id)
        examination = db.scalars(exam_stmt).first()
        if not examination:
            raise ValueError(f"Examination '{answer_sheet.examination_id}' not found")

        q_stmt = (
            select(Question)
            .where(Question.examination_id == examination.id)
            .order_by(Question.question_number)
        )
        questions = list(db.scalars(q_stmt).all())

        # 2. Extract and save original pages
        extracted_pages = extract_pages_from_file(file_bytes, extension, dirs["original"])
        answer_sheet.page_count = len(extracted_pages)

        # 3. Process each page: Preprocessing and OCR
        pages_data_for_segmentation = []
        created_pages = []

        for idx, (orig_page_path, pil_img) in enumerate(extracted_pages):
            page_num = idx + 1
            
            # Load into OpenCV
            cv_img = load_image_from_path(orig_page_path)
            h, w = cv_img.shape[:2]

            # Preprocess
            processed_img = preprocess_page(cv_img)
            proc_filename = f"page_{page_num}_processed.png"
            proc_path = str((dirs["processed"] / proc_filename).resolve())
            save_image(processed_img, proc_path)

            # OCR
            ocr_res = extract_ocr_data(processed_img)
            ocr_text = ocr_res.get("text", "")
            ocr_conf = ocr_res.get("confidence")
            word_boxes = ocr_res.get("word_boxes", [])

            # Create AnswerPage DB record
            page_record = AnswerPage(
                id=str(uuid.uuid4()),
                answer_sheet_id=answer_sheet.id,
                page_number=page_num,
                image_path=orig_page_path,
                processed_image_path=proc_path,
                ocr_text=ocr_text,
                ocr_confidence=ocr_conf,
                width=w,
                height=h,
                status="PROCESSED" if ocr_res.get("success") else "FAILED",
                error_message=ocr_res.get("error"),
            )
            db.add(page_record)
            created_pages.append(page_record)

            pages_data_for_segmentation.append({
                "page_id": page_record.id,
                "page_number": page_num,
                "image": cv_img,
                "processed_image": processed_img,
                "word_boxes": word_boxes,
                "ocr_text": ocr_text,
                "ocr_confidence": ocr_conf,
            })

        # Flush to ensure page_records have IDs persisted
        db.flush()

        # 4. Question Segmentation
        answer_segments, requires_review = segment_answer_sheet(
            pages_data=pages_data_for_segmentation,
            expected_questions=questions,
            crops_dir=dirs["crops"],
        )

        # 5. Create Answer records
        for seg in answer_segments:
            ans_record = Answer(
                id=str(uuid.uuid4()),
                answer_sheet_id=answer_sheet.id,
                question_id=seg["question_id"],
                answer_page_id=seg.get("answer_page_id"),
                crop_image_path=seg.get("crop_image_path"),
                ocr_text=seg.get("ocr_text"),
                corrected_text=None,
                ocr_confidence=seg.get("ocr_confidence"),
                segmentation_confidence=seg.get("segmentation_confidence"),
                status=seg["status"],
            )
            db.add(ans_record)

        # 6. Determine final AnswerSheet status
        if requires_review:
            answer_sheet.processing_status = ProcessingStatus.REVIEW_REQUIRED
        else:
            answer_sheet.processing_status = ProcessingStatus.PROCESSED

        db.commit()
        db.refresh(answer_sheet)
        return answer_sheet

    except Exception as e:
        logger.error(f"Processing failed for AnswerSheet '{answer_sheet_id}': {e}", exc_info=True)
        db.rollback()
        # Re-fetch answer_sheet to update failed status
        answer_sheet = db.scalars(select(AnswerSheet).where(AnswerSheet.id == answer_sheet_id)).first()
        if answer_sheet:
            answer_sheet.processing_status = ProcessingStatus.FAILED
            answer_sheet.error_message = str(e)
            db.commit()
            db.refresh(answer_sheet)
        raise
