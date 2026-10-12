"""Orchestrates: page preprocessing -> OCR -> marker detection -> crop regions -> crops -> per-answer OCR -> DB.

Honest failure handling: every failure is recorded (sheet FAILED / answer NEEDS_CORRECTION / OCR FAILED) - no result
is ever fabricated. Originals are never modified."""
from __future__ import annotations

import logging
import re
import uuid

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.cv import cropper
from app.cv.debug import draw_debug_page
from app.cv.preprocessing import (denoise, enhance_contrast, first_ink_row, ink_ratio, last_ink_row, load_image,
                                  preprocess_for_ocr, to_grayscale)
from app.cv.question_detector import (detect_question_markers, extract_ocr_data, select_marker_sequence)
from app.models import (Answer, AnswerSheet, AssignStatus, Evaluation, FacultyAssignment, Question, SegStatus,
                        SheetStatus)
from app.services.audit_service import log_action
from app.services.ocr_service import OCRResult, get_ocr_provider
from app.services.storage_service import get_storage

log = logging.getLogger("evalai.segmentation")


class ProcessingError(Exception):
    pass


class LockedError(ProcessingError):
    """Sheet has answers already assigned/evaluated; reprocessing would destroy evaluation history."""


def confidence_label(c: float) -> str:
    return "High" if c >= 0.75 else "Medium" if c >= 0.55 else "Low"


def _answer_locked(db: Session, answer_id) -> bool:
    has_assign = db.scalar(select(FacultyAssignment.id).where(
        FacultyAssignment.answer_id == answer_id, FacultyAssignment.status != AssignStatus.CANCELLED).limit(1))
    has_eval = db.scalar(select(Evaluation.id).where(Evaluation.answer_id == answer_id).limit(1))
    return bool(has_assign or has_eval)


def ocr_crop(crop: np.ndarray) -> OCRResult:
    """OCR a cropped answer (grey, denoised, CLAHE; upscaled when small). Failure is returned, never hidden."""
    gray = enhance_contrast(denoise(to_grayscale(crop)))
    h, w = gray.shape[:2]
    if w < 1400:
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    return get_ocr_provider().extract(gray, psm=6)


def _is_blank(crop: np.ndarray, marker_box: tuple[int, int, int, int] | None) -> bool:
    """Blank = no ink anywhere in the crop once the marker's own bounding box is masked out.
    (Answers often start on the same line as the marker, so only the marker box may be ignored.)"""
    body = crop.copy()
    if marker_box is not None:
        x0, y0, x1, y1 = marker_box
        body[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = 255
    return ink_ratio(body) < 0.0015


def _apply_ocr(answer: Answer, crop: np.ndarray, marker_box: tuple[int, int, int, int] | None, meta: dict) -> None:
    if _is_blank(crop, marker_box):
        answer.ocr_status, answer.extracted_text, answer.ocr_confidence = "BLANK", "", None
        answer.original_ocr_text = ""
        meta["note"] = "No handwriting detected below the question marker (blank answer)."
        return
    res = ocr_crop(crop)
    answer.ocr_status = res.status
    answer.extracted_text = res.text or ""
    answer.original_ocr_text = res.text or ""
    answer.ocr_confidence = res.confidence
    if res.error:
        meta["ocr_error"] = res.error


def process_answer_sheet(db: Session, sheet_id: uuid.UUID, actor_id: uuid.UUID | None = None) -> AnswerSheet:
    s = get_settings()
    storage = get_storage()
    sheet = db.get(AnswerSheet, sheet_id)
    if sheet is None:
        raise ProcessingError("Answer sheet not found")
    if sheet.student_id is None:
        raise ProcessingError("Map this answer sheet to a student before processing")

    old = list(db.scalars(select(Answer).where(Answer.answer_sheet_id == sheet.id)))
    if any(_answer_locked(db, a.id) for a in old):
        raise LockedError("Some answers on this sheet are already assigned or evaluated; reprocessing is blocked "
                          "to protect evaluation history. Use manual correction instead.")
    for a in old:
        storage.delete(a.image_path)
        db.delete(a)
    sheet.processing_status = SheetStatus.PROCESSING
    sheet.processing_message = None
    db.commit()

    try:
        questions = list(db.scalars(select(Question).where(Question.examination_id == sheet.examination_id)
                                    .order_by(Question.question_number)))
        if not questions:
            raise ProcessingError("Examination has no configured questions")
        configured = {q.question_number for q in questions}
        provider = get_ocr_provider()

        pages = []
        all_markers = []
        for page in sheet.pages:
            P = preprocess_for_ocr(load_image(storage.resolve(page.image_path)))
            H, W = P.color.shape[:2]
            words = extract_ocr_data(P.gray_enhanced, provider, s.seg_left_margin_frac)
            det = detect_question_markers(words, W, H, configured, page.page_number, s.seg_marker_min_conf,
                                          s.seg_left_margin_frac)
            pages.append((page, P, det))
            all_markers += det.markers
        chosen, rejected_seq = select_marker_sequence(all_markers)

        # Build parts per question, in reading order; continuation regions attach to the open question.
        parts: dict[int, list[tuple[int, np.ndarray, cropper.Region]]] = {}
        marker_of: dict[int, object] = {}
        open_q: int | None = None
        notes: list[str] = []
        for page, P, det in pages:
            H, W = P.color.shape[:2]
            pm = sorted([m for m in chosen if m.page_number == page.page_number], key=lambda m: m.y)
            regions = cropper.calculate_crop_regions(pm, H, last_ink_row(P.gray_enhanced), s.seg_top_padding,
                                                     s.seg_bottom_padding, s.seg_separator_padding,
                                                     ink_top=first_ink_row(P.gray_enhanced))
            for r in regions:
                if r.question_number is None:
                    if open_q is None:
                        continue  # header area above the very first marker
                    qn = open_q
                else:
                    qn = r.question_number
                    open_q = qn
                    marker_of[qn] = r.marker
                parts.setdefault(qn, []).append((page.page_number, cropper.crop_answer(P.color, r.y0, r.y1), r))
            if not pm and open_q is None and last_ink_row(P.gray_enhanced) > 60:
                notes.append(f"Page {page.page_number}: no question markers and no preceding question")

            # persist processed + debug images and per-page metadata
            sheet_tag = str(sheet.id)[:8]
            page.processed_image_path = storage.save_array("processed", f"{sheet_tag}_p{page.page_number}_processed",
                                                           P.binary)
            dbg = draw_debug_page(P.color, pm, regions, det.rejected)
            page.debug_image_path = storage.save_array("debug", f"{sheet_tag}_p{page.page_number}_debug", dbg)
            page.width, page.height, page.deskew_angle = W, H, P.angle
            page.markers_json = {"markers": [m.to_dict() for m in pm],
                                 "rejected": det.rejected + [r for r in rejected_seq
                                                             if r.get("page_number") == page.page_number],
                                 "regions": [{"question_number": r.question_number, "y0": r.y0, "y1": r.y1}
                                             for r in regions]}

        exam_tag = f"EXAM{str(sheet.examination_id)[:6]}"
        stu = sheet.student
        stu_tag = f"STU{stu.register_number}" if stu else "STUNA"
        prev_q = 0
        needs = False
        for q in questions:
            qn = q.question_number
            meta: dict = {"method": "AUTO"}
            if qn not in parts:
                needs = True
                meta["reason"] = "Question marker not detected - use manual segmentation"
                db.add(Answer(answer_sheet_id=sheet.id, student_id=sheet.student_id, question_id=q.id,
                              segmentation_status=SegStatus.NEEDS_CORRECTION, segmentation_confidence=0.0,
                              segmentation_label="Low", ocr_status="PENDING", segmentation_meta=meta))
                continue
            plist = parts[qn]
            merged = cropper.merge_multipage_answer([p[1] for p in plist])
            fname = f"{exam_tag}_{stu_tag}_Q{qn}_{str(sheet.id)[:8]}"
            img_path = storage.save_array("segmented", fname, merged)
            marker = marker_of[qn]
            pnums = [p[0] for p in plist]
            marker_conf = marker.confidence
            order_factor = 1.0 if qn > prev_q else 0.85
            prev_q = max(prev_q, qn)
            first_region = plist[0][2]
            mb = None
            if first_region.marker is marker:
                ry = marker.y - first_region.y0
                mb = (marker.x - 8, ry - 8, marker.x + marker.width + 8, ry + marker.height + 8)
            ans = Answer(answer_sheet_id=sheet.id, student_id=sheet.student_id, question_id=q.id,
                         page_start=min(pnums), page_end=max(pnums), image_path=img_path,
                         segmentation_status=SegStatus.DETECTED)
            meta.update({"marker": marker.to_dict(), "regions": [{"page": p[0], "y0": p[2].y0, "y1": p[2].y1}
                                                                for p in plist],
                         "continuation_pages": sorted(set(pnums) - {marker.page_number})})
            _apply_ocr(ans, merged, mb, meta)
            ink_factor = 0.6 if ans.ocr_status == "BLANK" else 1.0
            conf = round(float(marker_conf * order_factor * ink_factor), 3)
            ans.segmentation_confidence = conf
            ans.segmentation_label = confidence_label(conf)
            if ans.segmentation_label == "Low":
                ans.segmentation_status = SegStatus.NEEDS_CORRECTION
                needs = True
            ans.segmentation_meta = meta
            pg = next((p for p, _, _ in pages if p.page_number == marker.page_number), None)
            ans.debug_image_path = pg.debug_image_path if pg else None
            db.add(ans)

        sheet.processing_status = SheetStatus.NEEDS_REVIEW if (needs or notes) else SheetStatus.PROCESSED
        sheet.processing_message = "; ".join(notes) or ("Some answers need correction" if needs else None)
        log_action(db, actor_id, "sheet.processed", "AnswerSheet", sheet.id,
                   {"status": sheet.processing_status, "markers_found": len(chosen), "questions": len(questions)})
        db.commit()
    except LockedError:
        raise
    except Exception as exc:  # explicit failure: keep originals, record reason
        log.exception("Processing failed for sheet %s", sheet_id)
        db.rollback()
        sheet = db.get(AnswerSheet, sheet_id)
        sheet.processing_status = SheetStatus.FAILED
        sheet.processing_message = f"{type(exc).__name__}: {exc}"[:500]
        log_action(db, actor_id, "sheet.processing_failed", "AnswerSheet", sheet.id, {"error": sheet.processing_message})
        db.commit()
    return sheet


def manual_segment(db: Session, sheet_id: uuid.UUID, question_id: uuid.UUID, regions: list[dict],
                   actor_id: uuid.UUID | None = None) -> Answer:
    """Admin-defined crop: regions=[{page_number, y_start, y_end}, ...] in processed-page (deskewed) coordinates.
    Replaces any existing (un-evaluated) answer for that question. Confidence is recorded as manual."""
    storage = get_storage()
    sheet = db.get(AnswerSheet, sheet_id)
    if sheet is None:
        raise ProcessingError("Answer sheet not found")
    q = db.get(Question, question_id)
    if q is None or q.examination_id != sheet.examination_id:
        raise ProcessingError("Question does not belong to this examination")
    if not regions:
        raise ProcessingError("At least one region is required")
    existing = db.scalar(select(Answer).where(Answer.answer_sheet_id == sheet.id, Answer.question_id == q.id))
    if existing and _answer_locked(db, existing.id):
        raise LockedError("This answer is already assigned/evaluated and cannot be re-segmented")
    pages = {p.page_number: p for p in sheet.pages}
    crops = []
    for r in sorted(regions, key=lambda r: (r["page_number"], r["y_start"])):
        page = pages.get(r["page_number"])
        if page is None:
            raise ProcessingError(f"Page {r['page_number']} does not exist")
        # Same frame as automatic processing: normalise size, then apply the stored deskew angle.
        img = preprocess_for_ocr(load_image(storage.resolve(page.image_path)), angle=page.deskew_angle or 0.0).color
        y0, y1 = int(r["y_start"]), int(r["y_end"])
        if y1 - y0 < 10 or y0 < 0 or y1 > img.shape[0]:
            raise ProcessingError("Invalid crop boundaries")
        crops.append(cropper.crop_answer(img, y0, y1))
    merged = cropper.merge_multipage_answer(crops)
    stu = sheet.student
    fname = (f"EXAM{str(sheet.examination_id)[:6]}_STU{stu.register_number if stu else 'NA'}_Q{q.question_number}"
             f"_{str(sheet.id)[:8]}_manual")
    img_path = storage.save_array("segmented", fname, merged)
    meta = {"method": "MANUAL", "regions": regions, "by": str(actor_id) if actor_id else None}
    if existing:
        storage.delete(existing.image_path) if existing.image_path != img_path else None
        ans = existing
    else:
        ans = Answer(answer_sheet_id=sheet.id, student_id=sheet.student_id, question_id=q.id)
        db.add(ans)
    pn = [r["page_number"] for r in regions]
    ans.image_path, ans.page_start, ans.page_end = img_path, min(pn), max(pn)
    ans.ocr_corrected = False
    _apply_ocr(ans, merged, None, meta)
    ans.segmentation_confidence, ans.segmentation_label = 1.0, "High"
    ans.segmentation_status = SegStatus.DETECTED  # admin must still approve
    ans.segmentation_meta = meta
    log_action(db, actor_id, "segmentation.manual", "Answer", ans.id or "new", {"question": q.question_number})
    sheet_answers = list(db.scalars(select(Answer).where(Answer.answer_sheet_id == sheet.id)))
    if all(a.segmentation_status != SegStatus.NEEDS_CORRECTION for a in sheet_answers if a is not ans):
        if sheet.processing_status == SheetStatus.NEEDS_REVIEW:
            sheet.processing_status = SheetStatus.PROCESSED
    db.commit()
    return ans


def strip_marker_prefix(text: str) -> str:
    """OCR normalisation for AI scoring: remove a leading question marker ('Q1', 'Question 2:', '3.')."""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"^\s*(?:question|ques|qn|q)[\s.\-_:]*\d{1,2}\s*[.:)\-]?\s*", "", t, flags=re.I)
    t = re.sub(r"^\s*\d{1,2}\s*[.)]\s*", "", t)
    return t.strip()
