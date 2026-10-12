"""Question-level assignment engine.

Eligibility: faculty active AND available AND teaches the exam's subject AND below max_active_assignments.
Selection key (lowest wins): (answers of the SAME student already given to this faculty in this run,
load/capacity, least-recently-assigned, id). So one student's questions are spread over different faculty where a
reasonable alternative exists, load is balanced, and ties rotate round-robin. Deterministic."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (Answer, AssignStatus, Evaluation, Examination, FacultyAssignment, FacultyAvailability,
                        FacultySubject, Question, Role, SegStatus, User)
from app.services.audit_service import log_action


@dataclass
class Candidate:
    id: uuid.UUID
    name: str
    load: int
    capacity: int
    last_assigned: int = -1


def pick_faculty(cands: list[Candidate], same_student: dict[uuid.UUID, int]) -> Candidate | None:
    elig = [c for c in cands if c.capacity > 0 and c.load < c.capacity]
    if not elig:
        return None
    return min(elig, key=lambda c: (same_student.get(c.id, 0), c.load / c.capacity, c.last_assigned, str(c.id)))


def active_load(db: Session, faculty_id) -> int:
    return db.scalar(select(func.count(FacultyAssignment.id)).where(
        FacultyAssignment.faculty_id == faculty_id, FacultyAssignment.status.in_(AssignStatus.ACTIVE))) or 0


def ensure_availability(db: Session, faculty_id) -> FacultyAvailability:
    av = db.scalar(select(FacultyAvailability).where(FacultyAvailability.faculty_id == faculty_id))
    if av is None:
        av = FacultyAvailability(faculty_id=faculty_id)
        db.add(av)
        db.flush()
    return av


def sync_workload(db: Session, faculty_id) -> int:
    av = ensure_availability(db, faculty_id)
    av.current_assignment_count = active_load(db, faculty_id)
    return av.current_assignment_count


def eligible_faculty(db: Session, subject_id) -> list[User]:
    return list(db.scalars(select(User).join(FacultySubject, FacultySubject.faculty_id == User.id).where(
        User.role == Role.FACULTY, User.is_active.is_(True), FacultySubject.subject_id == subject_id)
        .order_by(User.full_name, User.id)))


def auto_assign(db: Session, exam_id: uuid.UUID, actor_id=None) -> dict:
    exam = db.get(Examination, exam_id)
    if exam is None:
        raise ValueError("Examination not found")
    cands: list[Candidate] = []
    skipped = []
    for f in eligible_faculty(db, exam.subject_id):
        av = ensure_availability(db, f.id)
        if not av.is_available:
            skipped.append({"faculty": f.full_name, "reason": "marked unavailable"})
            continue
        cands.append(Candidate(f.id, f.full_name, sync_workload(db, f.id), av.max_active_assignments))
    assigned_ids = select(FacultyAssignment.answer_id).where(
        FacultyAssignment.assignment_type == "PRIMARY",
        FacultyAssignment.status.in_((*AssignStatus.ACTIVE, AssignStatus.COMPLETED)))
    answers = list(db.scalars(
        select(Answer).join(Question, Question.id == Answer.question_id).join(
            Examination, Examination.id == Question.examination_id).where(
            Question.examination_id == exam_id, Answer.segmentation_status == SegStatus.READY,
            Answer.image_path.is_not(None), Answer.id.not_in(assigned_ids))
        .order_by(Answer.student_id, Question.question_number)))
    same: dict[uuid.UUID, dict[uuid.UUID, int]] = {}
    counter = 0
    created, unassigned = 0, []
    for a in answers:
        st = same.setdefault(a.student_id, {})
        c = pick_faculty(cands, st)
        if c is None:
            reason = ("no eligible faculty for this subject" if not cands
                      else "all eligible faculty are at maximum workload")
            unassigned.append({"answer_id": str(a.id), "reason": reason})
            continue
        db.add(FacultyAssignment(answer_id=a.id, faculty_id=c.id, assignment_type="PRIMARY"))
        c.load += 1
        c.last_assigned = counter
        counter += 1
        st[c.id] = st.get(c.id, 0) + 1
        created += 1
    for c in cands:
        sync_workload(db, c.id)
    if created and exam.status in ("DRAFT", "READY", "PROCESSING"):
        exam.status = "EVALUATION"
    log_action(db, actor_id, "assignment.auto", "Examination", exam_id,
               {"assigned": created, "unassigned": len(unassigned), "eligible_faculty": len(cands)})
    db.commit()
    return {"assigned": created, "unassigned": unassigned, "skipped_faculty": skipped,
            "faculty_used": [{"faculty_id": str(c.id), "name": c.name, "load": c.load, "capacity": c.capacity}
                             for c in cands],
            "message": ("No eligible faculty available" if not cands else None)}


def reassign(db: Session, assignment_id, new_faculty_id=None, actor_id=None) -> FacultyAssignment:
    old = db.get(FacultyAssignment, assignment_id)
    if old is None:
        raise LookupError("Assignment not found")
    if old.status not in AssignStatus.ACTIVE:
        raise ValueError(f"Only active assignments can be reassigned (status {old.status})")
    answer = db.get(Answer, old.answer_id)
    exam = db.get(Question, answer.question_id).examination
    same_student = {}
    if new_faculty_id is None:
        cands = []
        for f in eligible_faculty(db, exam.subject_id):
            av = ensure_availability(db, f.id)
            if f.id != old.faculty_id and av.is_available:
                cands.append(Candidate(f.id, f.full_name, sync_workload(db, f.id), av.max_active_assignments))
        chosen = pick_faculty(cands, same_student)
        if chosen is None:
            raise ValueError("No alternative eligible faculty with capacity")
        new_faculty_id = chosen.id
    else:
        f = db.get(User, new_faculty_id)
        if f is None or f.role != Role.FACULTY or not f.is_active:
            raise ValueError("Target must be an active faculty member")
        if f.id == old.faculty_id:
            raise ValueError("Answer is already assigned to this faculty member")
        if db.get(FacultySubject, (f.id, exam.subject_id)) is None:
            raise ValueError("Target faculty is not eligible for this subject")
        av = ensure_availability(db, f.id)
        if not av.is_available or sync_workload(db, f.id) >= av.max_active_assignments:
            raise ValueError("Target faculty is unavailable or at maximum workload")
    # drafts by the previous evaluator are discarded (submitted evaluations are never touched)
    for d in db.scalars(select(Evaluation).where(Evaluation.answer_id == old.answer_id,
                                                 Evaluation.faculty_id == old.faculty_id, Evaluation.is_draft.is_(True))):
        db.delete(d)
    old.status = AssignStatus.REASSIGNED
    new = FacultyAssignment(answer_id=old.answer_id, faculty_id=new_faculty_id, assignment_type=old.assignment_type)
    db.add(new)
    db.flush()
    sync_workload(db, old.faculty_id)
    sync_workload(db, new_faculty_id)
    log_action(db, actor_id, "assignment.reassign", "Answer", old.answer_id,
               {"from": str(old.faculty_id), "to": str(new_faculty_id)})
    db.commit()
    return new
