import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import admin_only, admin_or_reviewer, ai_dict, eval_dict, get_db
from app.models import ReviewCase, User
from app.schemas.inputs import ReviewAssignIn, ReviewEscalateIn, ReviewResolveIn
from app.services import review_service
from app.services.discrepancy_service import latest_ai_evaluation, latest_submitted_evaluation
from app.services.evaluation_service import Conflict, NotFound

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

TRIGGER_LABEL = {"AI_HUMAN_DISCREPANCY": "Evaluation discrepancy detected", "LOW_AI_CONFIDENCE": "AI reference unavailable / low confidence",
                 "LOW_OCR_CONFIDENCE": "Low OCR confidence", "SEGMENTATION_ERROR": "Segmentation issue", "MANUAL_FLAG": "Manually flagged"}


def case_row(db: Session, c: ReviewCase, detail: bool = False) -> dict:
    ans = c.answer
    ev, ai = latest_submitted_evaluation(db, ans.id), latest_ai_evaluation(db, ans.id)
    d = {"id": str(c.id), "answer_id": str(ans.id), "trigger_type": c.trigger_type,
         "trigger_label": TRIGGER_LABEL.get(c.trigger_type, c.trigger_type), "priority": c.priority, "status": c.status,
         "discrepancy_value": c.discrepancy_value, "note": c.note, "question_number": ans.question.question_number,
         "max_marks": ans.question.max_marks, "register_number": ans.student.register_number if ans.student else None,
         "student_name": ans.student.name if ans.student else None, "faculty_marks": ev.marks_awarded if ev else None,
         "ai_marks": ai.ai_marks if ai else None, "ai_confidence": ai.confidence_score if ai else None,
         "reviewer_id": str(c.reviewer_id) if c.reviewer_id else None,
         "reviewer_name": c.reviewer.full_name if c.reviewer else None, "reviewer_marks": c.reviewer_marks,
         "reviewer_comments": c.reviewer_comments, "created_at": c.created_at.isoformat(),
         "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None}
    if detail:
        q = ans.question
        d.update({"question_text": q.question_text, "model_answer_text": q.model_answer_text, "rubric": q.rubric_json,
                  "extracted_text": ans.extracted_text, "ocr_status": ans.ocr_status, "ocr_confidence": ans.ocr_confidence,
                  "faculty_evaluation": {**eval_dict(ev), "faculty_name": ev.faculty.full_name} if ev else None,
                  "ai_evaluation": ai_dict(ai), "examination_name": q.examination.name})
    return d


@router.get("")
def list_cases(status: str | None = None, priority: str | None = None, db: Session = Depends(get_db),
               _: User = Depends(admin_or_reviewer)):
    q = select(ReviewCase).order_by(ReviewCase.created_at.desc())
    if status:
        q = q.where(ReviewCase.status == status)
    if priority:
        q = q.where(ReviewCase.priority == priority)
    return [case_row(db, c) for c in db.scalars(q)]


@router.get("/{case_id}")
def get_case(case_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(admin_or_reviewer)):
    c = db.get(ReviewCase, case_id)
    if not c:
        raise HTTPException(404, "Review case not found")
    return case_row(db, c, True)


def _wrap(fn, *a):
    try:
        return fn(*a)
    except NotFound as exc:
        raise HTTPException(404, str(exc))
    except Conflict as exc:
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/{case_id}/assign")
def assign(case_id: uuid.UUID, body: ReviewAssignIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return case_row(db, _wrap(review_service.assign_reviewer, db, case_id, body.reviewer_id, admin))


@router.post("/{case_id}/resolve")
def resolve(case_id: uuid.UUID, body: ReviewResolveIn, db: Session = Depends(get_db), user: User = Depends(admin_or_reviewer)):
    return case_row(db, _wrap(review_service.resolve, db, case_id, body.reviewer_marks, body.reviewer_comments, user))


@router.post("/{case_id}/escalate")
def escalate(case_id: uuid.UUID, body: ReviewEscalateIn | None = None, db: Session = Depends(get_db), user: User = Depends(admin_or_reviewer)):
    return case_row(db, _wrap(review_service.escalate, db, case_id, body.comments if body else None, user))
