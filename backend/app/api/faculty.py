import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import admin_only, any_user, faculty_only, get_db, student_label
from app.core.security import hash_password
from app.models import (Answer, AssignStatus, Evaluation, FacultyAssignment, FacultyAvailability, FacultySubject,
                        Question, Role, User)
from app.schemas.inputs import AvailabilityIn, FacultyUpdate
from app.services import analytics_service
from app.services.assignment_service import ensure_availability, sync_workload
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/faculty", tags=["faculty"])


def fd(db: Session, u: User) -> dict:
    av = ensure_availability(db, u.id) if u.role == Role.FACULTY else None
    return {"id": str(u.id), "full_name": u.full_name, "email": u.email, "role": u.role, "is_active": u.is_active,
            "subject_ids": [str(s.id) for s in u.subjects], "subjects": [s.name for s in u.subjects],
            "is_available": av.is_available if av else None,
            "max_active_assignments": av.max_active_assignments if av else None,
            "current_assignment_count": sync_workload(db, u.id) if av else None}


# ---- faculty-only: own queue (declared before /{id} routes so 'me' is not parsed as a UUID)
@router.get("/me/assignments")
def my_assignments(status: str | None = None, exam_id: uuid.UUID | None = None, db: Session = Depends(get_db),
                   user: User = Depends(faculty_only)):
    q = (select(FacultyAssignment).where(FacultyAssignment.faculty_id == user.id,
                                         FacultyAssignment.status.in_((*AssignStatus.ACTIVE, AssignStatus.COMPLETED)))
         .order_by(FacultyAssignment.assigned_at.desc()))
    if status:
        q = q.where(FacultyAssignment.status == status)
    out = []
    for a in db.scalars(q):
        ans = a.answer
        exam = ans.question.examination
        if exam_id and exam.id != exam_id:
            continue
        out.append({"assignment_id": str(a.id), "answer_id": str(ans.id), "status": a.status,
                    "assigned_at": a.assigned_at.isoformat(), "question_number": ans.question.question_number,
                    "max_marks": ans.question.max_marks, "examination_id": str(exam.id),
                    "examination_name": exam.name, "subject": exam.subject.name, "ocr_status": ans.ocr_status,
                    **{k: v for k, v in student_label(db, user, ans).items() if k == "candidate_code" or v}})
    return out


@router.get("/me/summary")
def my_summary(db: Session = Depends(get_db), user: User = Depends(faculty_only)):
    return analytics_service.faculty_summary(db, user.id)


@router.get("/me/history")
def my_history(db: Session = Depends(get_db), user: User = Depends(faculty_only)):
    evs = db.scalars(select(Evaluation).where(Evaluation.faculty_id == user.id, Evaluation.is_draft.is_(False))
                     .order_by(Evaluation.submitted_at.desc()))
    return [{"answer_id": str(e.answer_id), "marks_awarded": e.marks_awarded, "max_marks": e.max_marks,
             "question_number": e.answer.question.question_number, "comments": e.comments, "version": e.version,
             "submitted_at": e.submitted_at.isoformat() if e.submitted_at else None} for e in evs]


# ---- admin management
@router.get("")
def list_faculty(include_reviewers: bool = False, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    roles = (Role.FACULTY, Role.REVIEWER) if include_reviewers else (Role.FACULTY,)
    users = db.scalars(select(User).where(User.role.in_(roles)).order_by(User.full_name))
    out = [fd(db, u) for u in users]
    db.commit()
    return out


@router.get("/reviewers")
def list_reviewers(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return [{"id": str(u.id), "full_name": u.full_name, "email": u.email}
            for u in db.scalars(select(User).where(User.role == Role.REVIEWER, User.is_active.is_(True)))]


@router.put("/{faculty_id}")
def update_faculty(faculty_id: uuid.UUID, body: FacultyUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    u = db.get(User, faculty_id)
    if not u or u.role not in (Role.FACULTY, Role.REVIEWER):
        raise HTTPException(404, "Faculty not found")
    if body.full_name is not None:
        u.full_name = body.full_name
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.password:
        u.password_hash = hash_password(body.password)
    if body.subject_ids is not None:
        for fs in db.scalars(select(FacultySubject).where(FacultySubject.faculty_id == u.id)):
            db.delete(fs)
        db.flush()
        for sid in set(body.subject_ids):
            db.add(FacultySubject(faculty_id=u.id, subject_id=sid))
    log_action(db, admin.id, "faculty.updated", "User", u.id, {"is_active": u.is_active})
    db.commit()
    db.refresh(u)
    return fd(db, u)


@router.post("/{faculty_id}/availability")
def set_availability(faculty_id: uuid.UUID, body: AvailabilityIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    u = db.get(User, faculty_id)
    if not u or u.role != Role.FACULTY:
        raise HTTPException(404, "Faculty not found")
    av = ensure_availability(db, u.id)
    av.is_available, av.max_active_assignments = body.is_available, body.max_active_assignments
    log_action(db, admin.id, "faculty.availability", "User", u.id, body.model_dump())
    db.commit()
    return fd(db, u)
