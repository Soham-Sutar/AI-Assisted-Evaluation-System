from __future__ import annotations

import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_

from app.core.database import get_db
from app.core.security import hash_password
from app.api.deps import require_roles, get_current_active_user
from app.models.user import User, UserRole
from app.models.subject import Subject
from app.models.faculty_subject import FacultySubject
from app.models.assignment import Assignment, AssignmentStatus
from app.models.evaluation import Evaluation
from app.models.answer import Answer
from app.models.question import Question
from app.models.examination import Examination
from app.services import analytics_service

logger = logging.getLogger("evalai.api.faculty")

router = APIRouter(prefix="/faculty", tags=["Faculty Management"])


class FacultyUpdatePayload(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
    subject_ids: Optional[List[str]] = None


class AvailabilityPayload(BaseModel):
    is_available: bool = True
    max_active_assignments: int = 40


def _build_faculty_dict(db: Session, u: User) -> dict:
    active_count = (
        db.scalar(
            select(func.count(Assignment.id)).where(
                Assignment.faculty_id == u.id,
                Assignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS]),
            )
        )
        or 0
    )
    return {
        "id": u.id,
        "full_name": u.full_name,
        "email": u.email,
        "role": u.role.value,
        "is_active": u.is_active,
        "subject_ids": [fs.subject_id for fs in u.faculty_subjects],
        "subjects": [fs.subject.name for fs in u.faculty_subjects if fs.subject],
        "is_available": u.is_active,
        "max_active_assignments": 40,
        "current_assignment_count": active_count,
    }


# ---- Faculty Self Queue & Workload Endpoints (declared before /{faculty_id}) ----

@router.get("/me/assignments")
def my_assignments(
    status: Optional[str] = None,
    exam_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
):
    """Faculty: List assigned evaluation work."""
    stmt = (
        select(Assignment)
        .where(
            Assignment.faculty_id == current_user.id,
            Assignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS, AssignmentStatus.COMPLETED]),
        )
        .order_by(Assignment.assigned_at.desc())
    )
    if status:
        stmt = stmt.where(Assignment.status == status)

    assignments = db.scalars(stmt).all()
    out = []
    for a in assignments:
        ans = a.answer
        if not ans:
            continue
        q = ans.question
        exam = q.examination if q else None
        if exam_id and exam and exam.id != exam_id:
            continue
        sheet = ans.answer_sheet
        cand_code = sheet.student.register_number if (sheet and sheet.student) else "CANDIDATE"

        out.append(
            {
                "assignment_id": a.id,
                "answer_id": ans.id,
                "status": a.status.value,
                "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
                "question_number": q.question_number if q else None,
                "max_marks": q.max_marks if q else None,
                "examination_id": exam.id if exam else None,
                "examination_name": exam.name if exam else None,
                "subject": exam.subject.name if (exam and exam.subject) else None,
                "ocr_status": "COMPLETED" if ans.ocr_text else "FAILED",
                "candidate_code": cand_code,
            }
        )
    return out


@router.get("/me/summary")
def my_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
):
    """Faculty: Overview progress counts for assigned evaluations."""
    return analytics_service.faculty_summary(db, current_user.id)


@router.get("/me/history")
def my_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
):
    """Faculty: History of submitted evaluations."""
    evs = db.scalars(
        select(Evaluation)
        .where(Evaluation.faculty_id == current_user.id)
        .order_by(Evaluation.submitted_at.desc())
    ).all()
    return [
        {
            "answer_id": e.answer_id,
            "marks_awarded": e.marks_awarded,
            "max_marks": e.max_marks,
            "question_number": e.answer.question.question_number if (e.answer and e.answer.question) else None,
            "comments": e.comments,
            "version": e.version,
            "submitted_at": e.submitted_at.isoformat() if e.submitted_at else None,
        }
        for e in evs
    ]


# ---- Admin Faculty Management Endpoints ----

@router.get("")
@router.get("/")
def list_faculty(
    include_reviewers: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: List faculty and reviewers with eligibility and workload."""
    roles = [UserRole.FACULTY, UserRole.REVIEWER] if include_reviewers else [UserRole.FACULTY]
    users = db.scalars(
        select(User).where(User.role.in_(roles)).order_by(User.full_name)
    ).all()
    return [_build_faculty_dict(db, u) for u in users]


@router.get("/reviewers")
def list_reviewers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: List active reviewers available for assignment."""
    users = db.scalars(
        select(User).where(User.role == UserRole.REVIEWER, User.is_active.is_(True)).order_by(User.full_name)
    ).all()
    return [{"id": u.id, "full_name": u.full_name, "email": u.email} for u in users]


@router.put("/{faculty_id}")
def update_faculty(
    faculty_id: str,
    payload: FacultyUpdatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Update faculty profile, active status, or subject eligibility."""
    u = db.get(User, faculty_id)
    if not u or u.role not in [UserRole.FACULTY, UserRole.REVIEWER]:
        raise HTTPException(status_code=404, detail="Faculty user not found")

    if payload.full_name is not None:
        u.full_name = payload.full_name.strip()
    if payload.is_active is not None:
        u.is_active = payload.is_active
    if payload.password:
        u.password_hash = hash_password(payload.password)

    if payload.subject_ids is not None:
        # Clear existing subject associations
        for fs in list(u.faculty_subjects):
            db.delete(fs)
        db.flush()
        # Add new subject associations
        for sid in set(payload.subject_ids):
            subj = db.get(Subject, sid)
            if subj:
                db.add(FacultySubject(faculty_id=u.id, subject_id=sid))

    db.commit()
    db.refresh(u)
    return _build_faculty_dict(db, u)


@router.post("/{faculty_id}/availability")
def set_availability(
    faculty_id: str,
    payload: AvailabilityPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Set availability and assignment capacity."""
    u = db.get(User, faculty_id)
    if not u or u.role != UserRole.FACULTY:
        raise HTTPException(status_code=404, detail="Faculty user not found")

    u.is_active = payload.is_available
    db.commit()
    db.refresh(u)
    return _build_faculty_dict(db, u)
