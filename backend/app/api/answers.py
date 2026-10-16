import os
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import require_roles, get_current_active_user
from app.models.user import User, UserRole
from app.models.answer import Answer, SegmentationStatus
from app.models.answer_sheet import AnswerSheet, ProcessingStatus
from app.models.question import Question
from app.models.evaluation import Evaluation
from app.models.ai_evaluation import AIEvaluation, AIEvaluationStatus
from app.schemas.answer import AnswerRead, AnswerCorrectionUpdate
from app.services.storage import verify_safe_path

logger = logging.getLogger("evalai.api.answers")

router = APIRouter(prefix="/answers", tags=["Answers"])


class OcrTextPayload(BaseModel):
    text: str


class SegmentationUpdatePayload(BaseModel):
    regions: Optional[List[Dict[str, Any]]] = None


def build_answer_read(
    ans: Answer,
    current_user: Optional[User] = None,
    db: Optional[Session] = None,
) -> AnswerRead:
    """Helper to convert Answer ORM object to AnswerRead schema with question, anti-anchored AI, and candidate metadata."""
    has_image = bool(ans.crop_image_path and os.path.isfile(ans.crop_image_path))
    extracted = ans.corrected_text if ans.corrected_text is not None else (ans.ocr_text or "")

    question = ans.question
    exam = question.examination if question else None
    sheet = ans.answer_sheet
    cand_code = sheet.student.register_number if (sheet and sheet.student) else "CANDIDATE"

    my_eval_dict = None
    ai_eval_dict = None

    if db and current_user:
        # Check human evaluation
        human_eval = db.scalars(
            select(Evaluation).where(
                Evaluation.answer_id == ans.id,
                Evaluation.faculty_id == current_user.id,
            )
        ).first()

        if human_eval:
            my_eval_dict = {
                "id": human_eval.id,
                "marks_awarded": human_eval.marks_awarded,
                "comments": human_eval.comments,
                "is_draft": False,
                "submitted_at": human_eval.submitted_at.isoformat() if human_eval.submitted_at else None,
            }

        # Check AI evaluation
        latest_ai = db.scalars(
            select(AIEvaluation)
            .where(AIEvaluation.answer_id == ans.id)
            .order_by(AIEvaluation.created_at.desc())
        ).first()

        # ANTI-ANCHORING RULE:
        # Faculty ONLY gets to see AI evaluation IF they have already submitted their human evaluation!
        can_see_ai = False
        if current_user.role in [UserRole.ADMIN, UserRole.REVIEWER]:
            can_see_ai = True
        elif current_user.role == UserRole.FACULTY and human_eval is not None:
            can_see_ai = True

        if can_see_ai and latest_ai:
            ai_eval_dict = {
                "status": latest_ai.status.value if hasattr(latest_ai.status, "value") else str(latest_ai.status),
                "ai_marks": latest_ai.ai_marks,
                "confidence_score": latest_ai.confidence_score,
                "model_name": latest_ai.model_name,
                "error_message": latest_ai.error_message,
            }

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
        question_number=question.question_number if question else None,
        question_text=question.question_text if question else None,
        max_marks=question.max_marks if question else None,
        has_image=has_image,
        extracted_text=extracted,
        segmentation_status=ans.status.value if hasattr(ans.status, "value") else str(ans.status),
        ocr_status="COMPLETED" if ans.ocr_text else "FAILED",
        ocr_corrected=bool(ans.corrected_text),
        candidate_code=cand_code,
        examination_name=exam.name if exam else None,
        subject=exam.subject.name if (exam and exam.subject) else None,
        model_answer_text=question.model_answer_text if question else None,
        rubric=question.rubric_json if question else None,
        my_evaluation=my_eval_dict,
        ai_evaluation=ai_eval_dict,
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
    return build_answer_read(ans, current_user=current_user, db=db)


@router.get("/{answer_id}/image")
def get_answer_image(
    answer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY, UserRole.REVIEWER)),
):
    """Securely stream cropped answer image with JWT authorization."""
    stmt = select(Answer).where(Answer.id == answer_id)
    ans = db.scalars(stmt).first()
    if not ans or not ans.crop_image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer crop image not found")

    try:
        safe_path = verify_safe_path(ans.crop_image_path)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid crop image path")

    if not safe_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop image file missing from disk")

    return FileResponse(safe_path, headers={"Cache-Control": "private, max-age=300"})


@router.post("/{answer_id}/approve", response_model=AnswerRead)
def approve_answer(
    answer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
):
    """Approve segmented answer ready for evaluation."""
    ans = db.get(Answer, answer_id)
    if not ans:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Answer '{answer_id}' not found")

    ans.status = SegmentationStatus.VERIFIED
    db.commit()
    db.refresh(ans)
    return build_answer_read(ans, current_user=current_user, db=db)


@router.post("/{answer_id}/needs-correction", response_model=AnswerRead)
def needs_correction_answer(
    answer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
):
    """Mark answer segmentation as needing manual correction."""
    ans = db.get(Answer, answer_id)
    if not ans:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Answer '{answer_id}' not found")

    ans.status = SegmentationStatus.NEEDS_REVIEW
    db.commit()
    db.refresh(ans)
    return build_answer_read(ans, current_user=current_user, db=db)


@router.put("/{answer_id}/ocr-text", response_model=AnswerRead)
def update_answer_ocr_text(
    answer_id: str,
    payload: OcrTextPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY, UserRole.REVIEWER)),
):
    """Correct or update OCR text for an answer without altering original OCR trace."""
    ans = db.get(Answer, answer_id)
    if not ans:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Answer '{answer_id}' not found")

    ans.corrected_text = payload.text.strip()
    db.commit()
    db.refresh(ans)
    return build_answer_read(ans, current_user=current_user, db=db)


@router.put("/{answer_id}/segmentation", response_model=AnswerRead)
def update_answer_segmentation(
    answer_id: str,
    payload: SegmentationUpdatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Apply manual crop adjustment."""
    ans = db.get(Answer, answer_id)
    if not ans:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Answer '{answer_id}' not found")

    ans.status = SegmentationStatus.CORRECTED
    db.commit()
    db.refresh(ans)
    return build_answer_read(ans, current_user=current_user, db=db)


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

    return build_answer_read(ans, current_user=current_user, db=db)
