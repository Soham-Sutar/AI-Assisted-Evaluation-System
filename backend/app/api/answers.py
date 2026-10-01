import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import require_roles
from app.models.user import User, UserRole
from app.models.answer import Answer, SegmentationStatus
from app.models.answer_sheet import AnswerSheet, ProcessingStatus
from app.models.question import Question
from app.schemas.answer import AnswerRead, AnswerCorrectionUpdate

logger = logging.getLogger("evalai.api.answers")

router = APIRouter(prefix="/answers", tags=["Answers"])


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


@router.get("/{answer_id}", response_model=AnswerRead)
def get_answer(
    answer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY, UserRole.REVIEWER)),
):
    """Retrieve details of a single segmented answer."""
    stmt = select(Answer).where(Answer.id == answer_id)
    ans = db.scalars(stmt).first()
    if not ans:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer with ID '{answer_id}' not found",
        )
    return build_answer_read(ans)


@router.put("/{answer_id}/correction", response_model=AnswerRead)
def correct_answer(
    answer_id: str,
    correction: AnswerCorrectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY, UserRole.REVIEWER)),
):
    """
    Manually correct question association, OCR text, or verification status of an answer.
    Preserves raw OCR text and original crop image for traceability.
    """
    stmt = select(Answer).where(Answer.id == answer_id)
    ans = db.scalars(stmt).first()
    if not ans:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer with ID '{answer_id}' not found",
        )

    # If re-associating to another question, verify question exists
    if correction.question_id and correction.question_id != ans.question_id:
        q_stmt = select(Question).where(Question.id == correction.question_id)
        new_q = db.scalars(q_stmt).first()
        if not new_q:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target question with ID '{correction.question_id}' not found",
            )
        # Ensure target question belongs to the same examination
        sheet = ans.answer_sheet
        if sheet and new_q.examination_id != sheet.examination_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target question does not belong to the same examination as this answer sheet",
            )
        ans.question_id = correction.question_id

    # Update corrected text (preserves raw ocr_text untouched)
    if correction.corrected_text is not None:
        ans.corrected_text = correction.corrected_text

    # Update status
    if correction.status is not None:
        ans.status = correction.status
    else:
        # Default to CORRECTED when text or question is modified
        ans.status = SegmentationStatus.CORRECTED

    db.commit()
    db.refresh(ans)

    # Check if all answers in the parent sheet are now resolved
    if ans.answer_sheet:
        all_answers = ans.answer_sheet.answers
        if all_answers and all(a.status != SegmentationStatus.NEEDS_REVIEW for a in all_answers):
            if ans.answer_sheet.processing_status == ProcessingStatus.REVIEW_REQUIRED:
                ans.answer_sheet.processing_status = ProcessingStatus.PROCESSED
                db.commit()

    return build_answer_read(ans)
