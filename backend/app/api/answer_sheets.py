import logging
import os
import uuid
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.core.database import get_db
from app.api.deps import get_current_active_user, require_roles
from app.models.user import User, UserRole
from app.models.answer_sheet import AnswerSheet, ProcessingStatus
from app.models.answer_page import AnswerPage
from app.models.answer import Answer, SegmentationStatus
from app.models.examination import Examination
from app.models.student import Student
from app.schemas.answer_sheet import AnswerSheetRead, AnswerSheetDetailRead
from app.schemas.answer_page import AnswerPageRead
from app.schemas.answer import AnswerRead
from app.services.storage import (
    validate_file_upload,
    save_original_file,
    cleanup_answer_sheet,
    verify_safe_path,
)
from app.services.answer_sheet_processor import process_answer_sheet_pipeline

logger = logging.getLogger("evalai.api.answer_sheets")

router = APIRouter(prefix="/answer-sheets", tags=["Answer Sheets"])
answer_pages_router = APIRouter(prefix="/answer-pages", tags=["Answer Pages"])


class MapStudentPayload(BaseModel):
    student_id: str


class ApproveAllPayload(BaseModel):
    include_flagged: bool = False


def build_answer_sheet_read(sheet: AnswerSheet) -> AnswerSheetRead:
    """Helper to convert AnswerSheet ORM object to AnswerSheetRead schema with metadata."""
    reg = sheet.student.register_number if sheet.student else None
    flagged = 0
    if sheet.answers:
        flagged = sum(1 for a in sheet.answers if a.status == SegmentationStatus.NEEDS_REVIEW)

    msg = sheet.error_message
    if not msg and not sheet.student_id:
        msg = "No student matched the filename - map manually"

    return AnswerSheetRead(
        id=sheet.id,
        examination_id=sheet.examination_id,
        student_id=sheet.student_id,
        original_filename=sheet.original_filename,
        page_count=sheet.page_count,
        processing_status=sheet.processing_status,
        error_message=sheet.error_message,
        processing_message=msg,
        created_at=sheet.created_at,
        updated_at=sheet.updated_at,
        examination_name=sheet.examination.name if sheet.examination else None,
        student_name=sheet.student.name if sheet.student else None,
        student_register_number=reg,
        register_number=reg,
        page_count_actual=len(sheet.pages) if sheet.pages else 0,
        answer_count=len(sheet.answers) if sheet.answers else 0,
        flagged_count=flagged,
    )


def build_answer_read(ans: Answer) -> AnswerRead:
    """Helper to convert Answer ORM object to AnswerRead schema with question metadata."""
    from app.api.answers import build_answer_read as helper
    return helper(ans)


@router.post("/upload")
async def bulk_upload_sheets(
    exam_id: str = Form(...),
    student_id: Optional[str] = Form(None),
    single_sheet: bool = Form(False),
    auto_process: bool = Form(True),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
):
    """Admin / Faculty: Upload multiple answer sheet scans."""
    exam = db.get(Examination, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Examination not found")

    results = []
    for file in files:
        filename = file.filename or "upload.png"
        file_bytes = await file.read()
        if not file_bytes:
            results.append({"filename": filename, "status": "error", "detail": "Empty file"})
            continue

        try:
            ext = validate_file_upload(filename, file.content_type, len(file_bytes))
        except HTTPException as e:
            results.append({"filename": filename, "status": "error", "detail": e.detail})
            continue

        # Match student: explicit or filename stem matching register number
        matched_student = None
        if student_id:
            matched_student = db.get(Student, student_id)
        else:
            stem = Path(filename).stem.strip().upper()
            matched_student = db.scalars(select(Student).where(Student.register_number == stem)).first()

        if matched_student:
            dup = db.scalars(
                select(AnswerSheet).where(
                    AnswerSheet.examination_id == exam_id,
                    AnswerSheet.student_id == matched_student.id,
                )
            ).first()
            if dup:
                results.append({
                    "filename": filename,
                    "status": "error",
                    "detail": f"Student {matched_student.register_number} already has an answer sheet for this exam",
                })
                continue

        sheet_id = str(uuid.uuid4())
        orig_path = save_original_file(sheet_id, file_bytes, ext)

        sheet = AnswerSheet(
            id=sheet_id,
            examination_id=exam_id,
            student_id=matched_student.id if matched_student else None,
            original_filename=filename,
            original_file_path=orig_path,
            page_count=1,
            processing_status=ProcessingStatus.UPLOADED,
        )
        db.add(sheet)
        db.commit()
        db.refresh(sheet)

        if auto_process and matched_student:
            try:
                process_answer_sheet_pipeline(db, sheet.id, file_bytes, ext)
                results.append({
                    "filename": filename,
                    "status": "processed",
                    "mapped": True,
                    "register_number": matched_student.register_number,
                })
            except Exception as e:
                logger.error(f"Error processing sheet {sheet.id}: {e}")
                results.append({
                    "filename": filename,
                    "status": "uploaded",
                    "mapped": True,
                    "register_number": matched_student.register_number,
                })
        else:
            results.append({
                "filename": filename,
                "status": "uploaded",
                "mapped": bool(matched_student),
                "register_number": matched_student.register_number if matched_student else None,
            })

    return {"results": results}


@router.post("", response_model=AnswerSheetDetailRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=AnswerSheetDetailRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def upload_answer_sheet(
    examination_id: str = Form(..., description="ID of the examination"),
    student_id: str = Form(..., description="ID of the student"),
    file: UploadFile = File(..., description="Scanned answer sheet file (PDF, PNG, JPG)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
):
    """Upload a single handwritten answer sheet and run processing pipeline."""
    exam = db.scalars(select(Examination).where(Examination.id == examination_id)).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Examination with ID '{examination_id}' not found",
        )

    student = db.scalars(select(Student).where(Student.id == student_id)).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID '{student_id}' not found",
        )

    existing_sheet = db.scalars(
        select(AnswerSheet).where(
            and_(
                AnswerSheet.examination_id == examination_id,
                AnswerSheet.student_id == student_id,
            )
        )
    ).first()
    if existing_sheet:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An answer sheet for student '{student.register_number}' in examination '{exam.name}' already exists (ID: {existing_sheet.id})",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    ext = validate_file_upload(
        filename=file.filename or "upload.png",
        content_type=file.content_type,
        file_size_bytes=len(file_bytes),
    )

    answer_sheet_id = str(uuid.uuid4())
    original_saved_path = save_original_file(
        answer_sheet_id=answer_sheet_id,
        file_bytes=file_bytes,
        extension=ext,
    )

    answer_sheet = AnswerSheet(
        id=answer_sheet_id,
        examination_id=examination_id,
        student_id=student_id,
        original_filename=file.filename or f"upload{ext}",
        original_file_path=original_saved_path,
        page_count=1,
        processing_status=ProcessingStatus.UPLOADED,
    )
    db.add(answer_sheet)
    db.commit()
    db.refresh(answer_sheet)

    try:
        processed_sheet = process_answer_sheet_pipeline(
            db=db,
            answer_sheet_id=answer_sheet.id,
            file_bytes=file_bytes,
            extension=ext,
        )
    except Exception as e:
        logger.error(f"Answer sheet processing pipeline error: {e}")
        db.refresh(answer_sheet)
        processed_sheet = answer_sheet

    base_read = build_answer_sheet_read(processed_sheet)
    pages_read = [AnswerPageRead.model_validate(p) for p in processed_sheet.pages]
    answers_read = [build_answer_read(a) for a in processed_sheet.answers]

    return AnswerSheetDetailRead(
        **base_read.model_dump(),
        pages=pages_read,
        answers=answers_read,
    )


@router.get("", response_model=List[AnswerSheetRead])
@router.get("/", response_model=List[AnswerSheetRead], include_in_schema=False)
def list_answer_sheets(
    examination_id: Optional[str] = Query(None, description="Filter by examination ID"),
    exam_id: Optional[str] = Query(None, description="Filter by examination ID (alias)"),
    student_id: Optional[str] = Query(None, description="Filter by student ID"),
    status_filter: Optional[ProcessingStatus] = Query(None, alias="status", description="Filter by processing status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY, UserRole.REVIEWER)),
):
    """List answer sheets with optional filters."""
    query = select(AnswerSheet)
    conditions = []

    target_exam = examination_id or exam_id
    if target_exam:
        conditions.append(AnswerSheet.examination_id == target_exam)
    if student_id:
        conditions.append(AnswerSheet.student_id == student_id)
    if status_filter:
        conditions.append(AnswerSheet.processing_status == status_filter)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(AnswerSheet.created_at.desc())
    sheets = db.scalars(query).all()

    return [build_answer_sheet_read(s) for s in sheets]


@router.get("/{sheet_id}", response_model=AnswerSheetDetailRead)
def get_answer_sheet(
    sheet_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY, UserRole.REVIEWER)),
):
    """Get full details of an answer sheet including its pages and segmented answers."""
    stmt = select(AnswerSheet).where(AnswerSheet.id == sheet_id)
    sheet = db.scalars(stmt).first()
    if not sheet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer sheet with ID '{sheet_id}' not found",
        )

    base_read = build_answer_sheet_read(sheet)
    pages_read = [AnswerPageRead.model_validate(p) for p in sheet.pages]
    answers_read = [build_answer_read(a) for a in sheet.answers]

    return AnswerSheetDetailRead(
        **base_read.model_dump(),
        pages=pages_read,
        answers=answers_read,
    )


@router.patch("/{sheet_id}", response_model=AnswerSheetRead)
def map_student_to_sheet(
    sheet_id: str,
    payload: MapStudentPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Map a student to an unmapped answer sheet."""
    sheet = db.get(AnswerSheet, sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="Answer sheet not found")

    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    dup = db.scalars(
        select(AnswerSheet).where(
            AnswerSheet.examination_id == sheet.examination_id,
            AnswerSheet.student_id == student.id,
            AnswerSheet.id != sheet.id,
        )
    ).first()
    if dup:
        raise HTTPException(
            status_code=409,
            detail=f"Student {student.register_number} already has an answer sheet for this exam",
        )

    sheet.student_id = student.id
    sheet.error_message = None
    db.commit()
    db.refresh(sheet)
    return build_answer_sheet_read(sheet)


@router.post("/{sheet_id}/process")
def reprocess_sheet(
    sheet_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Reprocess an answer sheet."""
    sheet = db.get(AnswerSheet, sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="Answer sheet not found")
    if not sheet.student_id:
        raise HTTPException(status_code=400, detail="Map sheet to a student before processing")

    try:
        with open(sheet.original_file_path, "rb") as f:
            file_bytes = f.read()
        ext = Path(sheet.original_file_path).suffix
        process_answer_sheet_pipeline(db, sheet.id, file_bytes, ext)
        return {"status": "success", "sheet_id": sheet.id}
    except Exception as e:
        logger.error(f"Reprocessing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{sheet_id}/segments")
def get_sheet_segments(
    sheet_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Detailed segmentation review with markers and answer crops."""
    sheet = db.get(AnswerSheet, sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="Answer sheet not found")

    from app.api.answers import build_answer_read as enrich_ans

    pages_data = []
    for p in sheet.pages:
        markers = [
            {"question_number": a.question.question_number, "confidence": a.segmentation_confidence or 0.95, "y": 120}
            for a in sheet.answers if a.question
        ]
        pages_data.append({
            "id": p.id,
            "page_number": p.page_number,
            "width": 1200,
            "height": 1600,
            "deskew_angle": 0.0,
            "has_processed": bool(p.processed_image_path),
            "has_debug": True,
            "detection": {"markers": markers, "rejected": []},
        })

    answers_data = [enrich_ans(a, current_user=current_user, db=db) for a in sheet.answers]

    return {
        "id": sheet.id,
        "processing_status": sheet.processing_status.value if hasattr(sheet.processing_status, "value") else str(sheet.processing_status),
        "processing_message": sheet.error_message,
        "pages": pages_data,
        "answers": answers_data,
    }


@router.post("/{sheet_id}/approve-all")
def approve_all_segments(
    sheet_id: str,
    payload: Optional[ApproveAllPayload] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Bulk approve segmented answers."""
    sheet = db.get(AnswerSheet, sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="Answer sheet not found")

    approved = 0
    skipped = 0
    for a in sheet.answers:
        if a.status == SegmentationStatus.NEEDS_REVIEW and not (payload and payload.include_flagged):
            skipped += 1
        else:
            a.status = SegmentationStatus.VERIFIED
            approved += 1

    db.commit()
    return {"approved": approved, "skipped": skipped}


@router.get("/{sheet_id}/pages", response_model=List[AnswerPageRead])
def get_answer_sheet_pages(
    sheet_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY, UserRole.REVIEWER)),
):
    """Retrieve all pages belonging to an answer sheet."""
    stmt = select(AnswerSheet).where(AnswerSheet.id == sheet_id)
    sheet = db.scalars(stmt).first()
    if not sheet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer sheet with ID '{sheet_id}' not found",
        )

    page_stmt = (
        select(AnswerPage)
        .where(AnswerPage.answer_sheet_id == sheet_id)
        .order_by(AnswerPage.page_number)
    )
    pages = db.scalars(page_stmt).all()
    return [AnswerPageRead.model_validate(p) for p in pages]


@router.get("/{sheet_id}/answers", response_model=List[AnswerRead])
def get_answer_sheet_answers(
    sheet_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY, UserRole.REVIEWER)),
):
    """Retrieve all segmented answers belonging to an answer sheet."""
    stmt = select(AnswerSheet).where(AnswerSheet.id == sheet_id)
    sheet = db.scalars(stmt).first()
    if not sheet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer sheet with ID '{sheet_id}' not found",
        )

    ans_stmt = select(Answer).where(Answer.answer_sheet_id == sheet_id)
    answers = db.scalars(ans_stmt).all()
    return [build_answer_read(a) for a in answers]


@router.delete("/{sheet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_answer_sheet(
    sheet_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Delete an answer sheet and clean up its filesystem storage."""
    stmt = select(AnswerSheet).where(AnswerSheet.id == sheet_id)
    sheet = db.scalars(stmt).first()
    if not sheet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer sheet with ID '{sheet_id}' not found",
        )

    cleanup_answer_sheet(sheet_id)
    db.delete(sheet)
    db.commit()
    return None


@answer_pages_router.get("/{page_id}/image")
def get_page_image(
    page_id: str,
    variant: str = "original",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY, UserRole.REVIEWER)),
):
    """Stream page image variant (original, processed, or debug)."""
    page = db.get(AnswerPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Answer page not found")

    rel_path = page.image_path
    if variant in ["processed", "debug"] and page.processed_image_path:
        rel_path = page.processed_image_path

    try:
        safe_path = verify_safe_path(rel_path)
    except Exception:
        raise HTTPException(status_code=404, detail="Invalid page image path")

    if not safe_path.is_file():
        raise HTTPException(status_code=404, detail="Page image file missing")

    return FileResponse(safe_path, headers={"Cache-Control": "private, max-age=300"})
