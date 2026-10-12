"""Answer-sheet upload, processing, segmentation review."""
from __future__ import annotations

import io
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import admin_only, answer_summary, get_db
from app.core.config import get_settings
from app.models import (Answer, AnswerPage, AnswerSheet, Examination, Question, SegStatus, SheetStatus, Student, User)
from app.schemas.inputs import ApproveAllIn, ManualSegmentIn, SheetMap
from app.services.audit_service import log_action
from app.services.segmentation_service import LockedError, ProcessingError, manual_segment, process_answer_sheet
from app.services.storage_service import ALLOWED_EXT, get_storage

log = logging.getLogger("evalai.upload")
router = APIRouter(prefix="/api", tags=["answer-sheets"])
MAX_PDF_PAGES = 30
CHUNK = 1024 * 1024


def sheet_dict(s: AnswerSheet, detail: bool = False) -> dict:
    d = {"id": str(s.id), "examination_id": str(s.examination_id), "student_id": str(s.student_id) if s.student_id else None,
         "register_number": s.student.register_number if s.student else None,
         "student_name": s.student.name if s.student else None, "original_filename": s.original_filename,
         "page_count": s.page_count, "processing_status": s.processing_status,
         "processing_message": s.processing_message, "created_at": s.created_at.isoformat(),
         "answer_count": len(s.answers),
         "flagged_count": sum(1 for a in s.answers if a.segmentation_status == SegStatus.NEEDS_CORRECTION)}
    if detail:
        d["pages"] = [{"id": str(p.id), "page_number": p.page_number, "width": p.width, "height": p.height,
                       "has_processed": bool(p.processed_image_path), "has_debug": bool(p.debug_image_path),
                       "deskew_angle": p.deskew_angle, "detection": p.markers_json} for p in s.pages]
        d["answers"] = [answer_summary(a) for a in sorted(s.answers, key=lambda a: a.question.question_number)]
    return d


def _safe_display_name(name: str | None) -> str:
    base = Path(name or "upload").name  # strips any directory component
    return "".join(c for c in base if c.isalnum() or c in "._- ")[:200] or "upload"


async def _read_limited(f: UploadFile, limit: int) -> bytes:
    buf = bytearray()
    while chunk := await f.read(CHUNK):
        buf += chunk
        if len(buf) > limit:
            raise HTTPException(413, f"File exceeds the {limit // (1024 * 1024)} MB limit")
    return bytes(buf)


def _validate_and_pages(data: bytes, ext: str) -> list[bytes]:
    """Verify real content (magic bytes / decoder), return per-page PNG/JPEG bytes (PDF pages rendered)."""
    if ext == ".pdf":
        if not data.startswith(b"%PDF"):
            raise ValueError("File content is not a valid PDF")
        import pymupdf
        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
        except Exception:
            raise ValueError("PDF could not be opened")
        if doc.page_count == 0 or doc.page_count > MAX_PDF_PAGES:
            raise ValueError(f"PDF must have 1-{MAX_PDF_PAGES} pages")
        return [doc[i].get_pixmap(dpi=200).tobytes("png") for i in range(doc.page_count)]
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            fmt = (im.format or "").upper()
            if fmt not in ("PNG", "JPEG"):
                raise ValueError("Only PNG and JPEG images are accepted")
            if im.width * im.height > 60_000_000:
                raise ValueError("Image dimensions too large")
    except ValueError:
        raise
    except Exception:
        raise ValueError("File content is not a valid image")
    return [data]


def _run_processing_bg(sheet_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        process_answer_sheet(db, sheet_id, actor_id)
    except Exception:
        log.exception("Background processing crashed for %s", sheet_id)
    finally:
        db.close()


@router.post("/answer-sheets/upload", status_code=201)
async def upload(background: BackgroundTasks, exam_id: uuid.UUID = Form(...), student_id: uuid.UUID | None = Form(None),
                 single_sheet: bool = Form(False), auto_process: bool = Form(True),
                 files: list[UploadFile] = File(...), db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    """Each file = one answer sheet, mapped to a student by filename (register number) or by `student_id`.
    With single_sheet=true all files are the pages of ONE sheet (requires student_id or a first-file filename match)."""
    s = get_settings()
    storage = get_storage()
    exam = db.get(Examination, exam_id)
    if exam is None:
        raise HTTPException(404, "Examination not found")
    if not files:
        raise HTTPException(422, "No files supplied")
    limit = s.max_upload_mb * 1024 * 1024
    staged = []  # (display_name, ext, original_bytes, page_bytes_list)
    results = []
    for f in files:
        name = _safe_display_name(f.filename)
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED_EXT:
            results.append({"filename": name, "status": "error", "detail": "Unsupported file type (use PNG, JPG or PDF)"})
            continue
        data = await _read_limited(f, limit)
        try:
            pages = _validate_and_pages(data, ext)
        except ValueError as exc:
            results.append({"filename": name, "status": "error", "detail": str(exc)})
            continue
        staged.append((name, ext, data, pages))

    def resolve_student(name: str, explicit: uuid.UUID | None):
        if explicit:
            return db.get(Student, explicit)
        stem = Path(name).stem
        return db.scalar(select(Student).where(Student.register_number.ilike(stem)))

    groups = [staged] if (single_sheet and staged) else [[x] for x in staged]
    for grp in groups:
        name = grp[0][0] if len(grp) == 1 else f"{grp[0][0]} (+{len(grp) - 1} pages)"
        stu = resolve_student(grp[0][0], student_id if (student_id and (single_sheet or len(staged) == 1)) else None)
        if student_id and not stu:
            results.append({"filename": name, "status": "error", "detail": "Student not found"})
            continue
        if stu and db.scalar(select(AnswerSheet.id).where(AnswerSheet.examination_id == exam_id,
                                                          AnswerSheet.student_id == stu.id).limit(1)):
            results.append({"filename": name, "status": "error",
                            "detail": f"Student {stu.register_number} already has an answer sheet for this exam"})
            continue
        all_pages = [pg for g in grp for pg in g[3]]
        first_ext = grp[0][1]
        orig_rel = storage.save_bytes("original", grp[0][2], first_ext)
        sheet = AnswerSheet(examination_id=exam_id, student_id=stu.id if stu else None, original_filename=name,
                            original_file_path=orig_rel, page_count=len(all_pages), uploaded_by=admin.id,
                            processing_status=SheetStatus.UPLOADED,
                            processing_message=None if stu else "No student matched the filename - map manually")
        db.add(sheet)
        db.flush()
        for i, pb in enumerate(all_pages, start=1):
            if i == 1 and len(grp) == 1 and first_ext != ".pdf":
                rel = orig_rel  # the untouched original is page 1
            else:
                is_png = pb[:4] == b"\x89PNG"
                rel = storage.save_bytes("original", pb, ".png" if is_png else ".jpg")
            db.add(AnswerPage(answer_sheet_id=sheet.id, page_number=i, image_path=rel))
        log_action(db, admin.id, "sheet.uploaded", "AnswerSheet", sheet.id,
                   {"filename": name, "pages": len(all_pages), "mapped": bool(stu)})
        db.commit()
        item = {"filename": name, "status": "uploaded", "sheet_id": str(sheet.id), "mapped": bool(stu),
                "register_number": stu.register_number if stu else None}
        if auto_process and stu:
            sheet.processing_status = SheetStatus.PROCESSING
            db.commit()
            background.add_task(_run_processing_bg, sheet.id, admin.id)
            item["status"] = "processing"
        results.append(item)
    return {"results": results}


@router.get("/answer-sheets")
def list_sheets(exam_id: uuid.UUID | None = None, status: str | None = None, db: Session = Depends(get_db),
                _: User = Depends(admin_only)):
    q = select(AnswerSheet).order_by(AnswerSheet.created_at.desc())
    if exam_id:
        q = q.where(AnswerSheet.examination_id == exam_id)
    if status:
        q = q.where(AnswerSheet.processing_status == status)
    return [sheet_dict(s) for s in db.scalars(q)]


def _sheet(db, sheet_id) -> AnswerSheet:
    s = db.get(AnswerSheet, sheet_id)
    if not s:
        raise HTTPException(404, "Answer sheet not found")
    return s


@router.get("/answer-sheets/{sheet_id}")
def get_sheet(sheet_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return sheet_dict(_sheet(db, sheet_id), True)


@router.get("/answer-sheets/{sheet_id}/segments")
def get_segments(sheet_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return sheet_dict(_sheet(db, sheet_id), True)


@router.patch("/answer-sheets/{sheet_id}")
def map_student(sheet_id: uuid.UUID, body: SheetMap, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    sheet = _sheet(db, sheet_id)
    if sheet.answers:
        raise HTTPException(409, "Sheet already has segmented answers; cannot change student")
    stu = db.get(Student, body.student_id)
    if not stu:
        raise HTTPException(404, "Student not found")
    if db.scalar(select(AnswerSheet.id).where(AnswerSheet.examination_id == sheet.examination_id,
                                              AnswerSheet.student_id == stu.id, AnswerSheet.id != sheet.id).limit(1)):
        raise HTTPException(409, "Student already has an answer sheet for this exam")
    sheet.student_id, sheet.processing_message = stu.id, None
    log_action(db, admin.id, "sheet.mapped", "AnswerSheet", sheet.id, {"student": stu.register_number})
    db.commit()
    return sheet_dict(sheet)


@router.post("/answer-sheets/{sheet_id}/process", status_code=202)
def process(sheet_id: uuid.UUID, background: BackgroundTasks, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    sheet = _sheet(db, sheet_id)
    if sheet.student_id is None:
        raise HTTPException(409, "Map this answer sheet to a student before processing")
    if sheet.processing_status == SheetStatus.PROCESSING:
        raise HTTPException(409, "Sheet is already being processed")
    for a in sheet.answers:
        from app.services.segmentation_service import _answer_locked
        if _answer_locked(db, a.id):
            raise HTTPException(409, "Answers on this sheet are already assigned/evaluated; reprocessing is blocked")
    sheet.processing_status = SheetStatus.PROCESSING
    db.commit()
    background.add_task(_run_processing_bg, sheet.id, admin.id)
    return {"status": "processing", "sheet_id": str(sheet.id)}


@router.post("/answer-sheets/{sheet_id}/approve-all")
def approve_all(sheet_id: uuid.UUID, body: ApproveAllIn | None = None, db: Session = Depends(get_db),
                admin: User = Depends(admin_only)):
    body = body or ApproveAllIn()
    sheet = _sheet(db, sheet_id)
    approved, skipped = 0, 0
    for a in sheet.answers:
        if not a.image_path:
            skipped += 1
        elif a.segmentation_status == SegStatus.NEEDS_CORRECTION and not body.include_flagged:
            skipped += 1
        elif a.segmentation_status in (SegStatus.DETECTED, SegStatus.NEEDS_CORRECTION):
            a.segmentation_status = SegStatus.READY
            approved += 1
    log_action(db, admin.id, "segmentation.approved_all", "AnswerSheet", sheet.id, {"approved": approved, "skipped": skipped})
    db.commit()
    return {"approved": approved, "skipped": skipped}


@router.post("/answer-sheets/{sheet_id}/segments/manual")
def manual(sheet_id: uuid.UUID, body: ManualSegmentIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    try:
        ans = manual_segment(db, sheet_id, body.question_id, [r.model_dump() for r in body.regions], admin.id)
    except LockedError as exc:
        raise HTTPException(409, str(exc))
    except ProcessingError as exc:
        raise HTTPException(422, str(exc))
    return answer_summary(ans)


@router.get("/answer-pages/{page_id}/image")
def page_image(page_id: uuid.UUID, variant: str = "original", db: Session = Depends(get_db), _: User = Depends(admin_only)):
    p = db.get(AnswerPage, page_id)
    if not p:
        raise HTTPException(404, "Page not found")
    rel = {"original": p.image_path, "processed": p.processed_image_path, "debug": p.debug_image_path}.get(variant)
    if not rel:
        raise HTTPException(404, "Image variant not available")
    path = get_storage().resolve(rel)
    if not path.is_file():
        raise HTTPException(404, "Image file missing")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=300"})
