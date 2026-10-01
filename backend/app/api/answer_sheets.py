import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.core.database import get_db
from app.api.deps import get_current_active_user, require_roles
from app.models.user import User, UserRole
from app.models.answer_sheet import AnswerSheet, ProcessingStatus
from app.models.answer_page import AnswerPage
from app.models.answer import Answer
from app.models.examination import Examination
from app.models.student import Student
from app.schemas.answer_sheet import AnswerSheetRead, AnswerSheetDetailRead
from app.schemas.answer_page import AnswerPageRead
from app.schemas.answer import AnswerRead
from app.services.storage import (
    validate_file_upload,
    save_original_file,
    cleanup_answer_sheet,
)
from app.services.answer_sheet_processor import process_answer_sheet_pipeline

logger = logging.getLogger("evalai.api.answer_sheets")

router = APIRouter(prefix="/answer-sheets", tags=["Answer Sheets"])


def build_answer_sheet_read(sheet: AnswerSheet) -> AnswerSheetRead:
    """Helper to convert AnswerSheet ORM object to AnswerSheetRead schema with metadata."""
    return AnswerSheetRead(
        id=sheet.id,
        examination_id=sheet.examination_id,
        student_id=sheet.student_id,
        original_filename=sheet.original_filename,
        page_count=sheet.page_count,
        processing_status=sheet.processing_status,
        error_message=sheet.error_message,
        created_at=sheet.created_at,
        updated_at=sheet.updated_at,
        examination_name=sheet.examination.name if sheet.examination else None,
        student_name=sheet.student.name if sheet.student else None,
        student_register_number=sheet.student.register_number if sheet.student else None,
        page_count_actual=len(sheet.pages) if sheet.pages else 0,
        answer_count=len(sheet.answers) if sheet.answers else 0,
    )


def build_answer_read(ans: Answer) -> AnswerRead:
    """Helper to convert Answer ORM object to AnswerRead schema with question metadata."""
    return AnswerRead(
        id=ans.id,
        answer_sheet_id=ans.answer_sheet_id,
        question_id=ans.question_id,
        answer_page_id=ans.answer_page_id,
        crop_image_path=ans.crop_image_path,
        ocr_text=ans.ocr_text,
        corrected_text=ans.corrected_text,
        ocr_confidence=ans.ocr_confidence,
        segmentation_confidence=ans.segmentation_confidence,
        status=ans.status,
        created_at=ans.created_at,
        updated_at=ans.updated_at,
        question_number=ans.question.question_number if ans.question else None,
        question_text=ans.question.question_text if ans.question else None,
        max_marks=ans.question.max_marks if ans.question else None,
    )


@router.post("/", response_model=AnswerSheetDetailRead, status_code=status.HTTP_201_CREATED)
async def upload_answer_sheet(
    examination_id: str = Form(..., description="ID of the examination"),
    student_id: str = Form(..., description="ID of the student"),
    file: UploadFile = File(..., description="Scanned answer sheet file (PDF, PNG, JPG)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
):
    """
    Upload a handwritten answer sheet, store the original file safely,
    and run preprocessing, OCR, and question segmentation.
    """
    # 1. Verify examination exists
    exam = db.scalars(select(Examination).where(Examination.id == examination_id)).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Examination with ID '{examination_id}' not found",
        )

    # 2. Verify student exists
    student = db.scalars(select(Student).where(Student.id == student_id)).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID '{student_id}' not found",
        )

    # 3. Check for existing answer sheet (unique examination + student)
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

    # 4. Read file bytes and validate extension / size / MIME
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

    # 5. Create initial AnswerSheet record
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

    # 6. Execute processing pipeline (Synchronous for Phase 3)
    try:
        processed_sheet = process_answer_sheet_pipeline(
            db=db,
            answer_sheet_id=answer_sheet.id,
            file_bytes=file_bytes,
            extension=ext,
        )
    except Exception as e:
        logger.error(f"Answer sheet processing pipeline error: {e}")
        # Processing status and error are already recorded in DB by the processor
        db.refresh(answer_sheet)
        processed_sheet = answer_sheet

    # Construct detailed response
    base_read = build_answer_sheet_read(processed_sheet)
    pages_read = [AnswerPageRead.model_validate(p) for p in processed_sheet.pages]
    answers_read = [build_answer_read(a) for a in processed_sheet.answers]

    return AnswerSheetDetailRead(
        **base_read.model_dump(),
        pages=pages_read,
        answers=answers_read,
    )


@router.get("/", response_model=List[AnswerSheetRead])
def list_answer_sheets(
    examination_id: Optional[str] = Query(None, description="Filter by examination ID"),
    student_id: Optional[str] = Query(None, description="Filter by student ID"),
    status_filter: Optional[ProcessingStatus] = Query(None, alias="status", description="Filter by processing status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY, UserRole.REVIEWER)),
):
    """List answer sheets with optional filters."""
    query = select(AnswerSheet)
    conditions = []

    if examination_id:
        conditions.append(AnswerSheet.examination_id == examination_id)
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

    ans_stmt = (
        select(Answer)
        .where(Answer.answer_sheet_id == sheet_id)
    )
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
