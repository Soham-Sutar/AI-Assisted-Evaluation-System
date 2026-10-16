import logging
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func

from app.core.database import get_db
from app.api.deps import get_current_active_user, require_roles
from app.models.user import User, UserRole
from app.models.assignment import Assignment, AssignmentStatus, AssignmentType
from app.models.answer import Answer, SegmentationStatus
from app.models.answer_sheet import AnswerSheet
from app.models.question import Question
from app.models.examination import Examination
from app.models.faculty_subject import FacultySubject
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate, AssignmentRead

logger = logging.getLogger("evalai.api.assignments")

router = APIRouter(prefix="/assignments", tags=["Assignments"])

# Statuses that indicate the answer is already under active assignment
_ACTIVE_STATUSES = {AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS}


def _enrich_assignment(assignment: Assignment) -> AssignmentRead:
    """Convert an Assignment ORM object to an enriched AssignmentRead schema."""
    faculty = assignment.faculty
    answer = assignment.answer
    question = answer.question if answer else None
    examination = question.examination if question else None

    student_reg = None
    if answer and answer.answer_sheet and answer.answer_sheet.student:
        student_reg = answer.answer_sheet.student.register_number

    return AssignmentRead(
        id=assignment.id,
        answer_id=assignment.answer_id,
        faculty_id=assignment.faculty_id,
        assignment_type=assignment.assignment_type,
        status=assignment.status,
        assigned_at=assignment.assigned_at,
        started_at=assignment.started_at,
        completed_at=assignment.completed_at,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
        faculty_name=faculty.full_name if faculty else None,
        faculty_email=faculty.email if faculty else None,
        question_number=question.question_number if question else None,
        examination_name=examination.name if examination else None,
        subject_name=examination.subject.name if (examination and examination.subject) else None,
        student_register_number=student_reg,
    )


def _verify_faculty_eligible(db: Session, faculty_id: str, answer: Answer) -> User:
    """
    Verify that the given faculty_id references a real, active FACULTY user who
    is associated with the subject of this answer's examination.
    Returns the verified faculty User.
    """
    faculty = db.scalars(select(User).where(User.id == faculty_id)).first()
    if not faculty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Faculty user with ID '{faculty_id}' not found",
        )
    if faculty.role != UserRole.FACULTY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User '{faculty_id}' does not have the FACULTY role",
        )
    if not faculty.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Faculty user '{faculty_id}' is inactive and cannot receive assignments",
        )

    # Verify subject eligibility via FacultySubject
    question = answer.question
    if not question:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Answer has no associated question — cannot determine subject eligibility",
        )
    examination = question.examination
    if not examination:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Answer's question has no associated examination",
        )
    subject_id = examination.subject_id

    eligibility = db.scalars(
        select(FacultySubject).where(
            and_(
                FacultySubject.faculty_id == faculty_id,
                FacultySubject.subject_id == subject_id,
            )
        )
    ).first()
    if not eligibility:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Faculty '{faculty_id}' is not eligible for subject '{subject_id}'. "
                "Associate the faculty with the subject first."
            ),
        )
    return faculty


# ---------------------------------------------------------------------------
# ADMIN ENDPOINTS
# ---------------------------------------------------------------------------

@router.post("", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_assignment(
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: assign a segmented answer to an eligible faculty member."""
    # Resolve answer
    answer = db.scalars(select(Answer).where(Answer.id == payload.answer_id)).first()
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer with ID '{payload.answer_id}' not found",
        )

    # Verify faculty eligibility (role, active, subject association)
    _verify_faculty_eligible(db, payload.faculty_id, answer)

    # Check for duplicate active assignment
    existing = db.scalars(
        select(Assignment).where(
            and_(
                Assignment.answer_id == payload.answer_id,
                Assignment.faculty_id == payload.faculty_id,
                Assignment.assignment_type == payload.assignment_type,
                Assignment.status.in_(list(_ACTIVE_STATUSES)),
            )
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"An active assignment of type '{payload.assignment_type}' already exists "
                f"for this answer and faculty (ID: {existing.id})"
            ),
        )

    # Question-wise allocation check: ensure this question is not already assigned to another faculty
    question = answer.question
    if question:
        conflicting = db.scalars(
            select(Assignment)
            .join(Answer, Answer.id == Assignment.answer_id)
            .where(
                Answer.question_id == question.id,
                Assignment.faculty_id != payload.faculty_id,
                Assignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS, AssignmentStatus.COMPLETED]),
            )
        ).first()
        if conflicting:
            fac_name = conflicting.faculty.full_name if conflicting.faculty else conflicting.faculty_id
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Question {question.question_number} is already assigned to {fac_name}. "
                    f"Question-wise faculty allocation requires all answers for Question "
                    f"{question.question_number} to be assigned to the same faculty member."
                ),
            )

    assignment = Assignment(
        answer_id=payload.answer_id,
        faculty_id=payload.faculty_id,
        assignment_type=payload.assignment_type,
        status=AssignmentStatus.ASSIGNED,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    logger.info(
        "Assignment created: %s (answer=%s faculty=%s type=%s)",
        assignment.id,
        payload.answer_id,
        payload.faculty_id,
        payload.assignment_type,
    )
    return _enrich_assignment(assignment)


from pydantic import BaseModel
from app.services import analytics_service


class AutoAssignPayload(BaseModel):
    exam_id: str


class ReassignPayload(BaseModel):
    faculty_id: Optional[str] = None


@router.get("", response_model=List[AssignmentRead])
@router.get("/", response_model=List[AssignmentRead], include_in_schema=False)
def list_assignments(
    faculty_id: Optional[str] = Query(None, description="Filter by faculty ID"),
    answer_id: Optional[str] = Query(None, description="Filter by answer ID"),
    exam_id: Optional[str] = Query(None, description="Filter by examination ID"),
    question_number: Optional[int] = Query(None, description="Filter by question number"),
    assignment_status: Optional[AssignmentStatus] = Query(None, alias="status"),
    assignment_type: Optional[AssignmentType] = Query(None, alias="type"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: list all assignments with optional filters."""
    query = select(Assignment)
    conditions = []
    if faculty_id:
        conditions.append(Assignment.faculty_id == faculty_id)
    if answer_id:
        conditions.append(Assignment.answer_id == answer_id)
    if assignment_status:
        conditions.append(Assignment.status == assignment_status)
    if assignment_type:
        conditions.append(Assignment.assignment_type == assignment_type)
    if conditions:
        query = query.where(and_(*conditions))
    query = query.order_by(Assignment.assigned_at.desc())
    assignments = db.scalars(query).all()

    # In-memory filter for exam_id and question_number if provided
    if exam_id or question_number:
        filtered = []
        for a in assignments:
            q = a.answer.question if a.answer else None
            if exam_id and (not q or q.examination_id != exam_id):
                continue
            if question_number and (not q or q.question_number != question_number):
                continue
            filtered.append(a)
        assignments = filtered

    return [_enrich_assignment(a) for a in assignments]


@router.get("/workload")
def get_faculty_workload(
    exam_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Retrieve faculty workload statistics."""
    return analytics_service.faculty_workload(db, exam_id)


@router.get("/unassigned")
def get_unassigned_answers(
    exam_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: List answers awaiting evaluation assignment."""
    assigned_subquery = select(Assignment.answer_id).where(
        Assignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS, AssignmentStatus.COMPLETED])
    )
    unassigned = db.scalars(
        select(Answer)
        .join(Question, Question.id == Answer.question_id)
        .where(
            Question.examination_id == exam_id,
            Answer.id.not_in(assigned_subquery),
        )
        .order_by(Question.question_number)
    ).all()

    out = []
    for a in unassigned:
        sheet = a.answer_sheet
        reg = sheet.student.register_number if (sheet and sheet.student) else "Unmapped"
        qn = a.question.question_number if a.question else 0
        reason = "Not yet assigned"
        if a.status == SegmentationStatus.NEEDS_REVIEW:
            reason = "Segmentation requires review"
        out.append({
            "answer_id": a.id,
            "register_number": reg,
            "question_number": qn,
            "reason": reason,
        })
    return out


@router.post("/auto-assign")
def run_auto_assign(
    payload: AutoAssignPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Admin: Automatically assign unassigned answers to eligible faculty
    using question-wise faculty allocation.

    Rules:
    - Each question number in the exam is allocated to exactly one eligible faculty member.
    - All answers for Q1 go to the faculty member for Q1; all answers for Q2 go to faculty for Q2, etc.
    - No question group is split across multiple faculty members.
    - Allocation across questions is deterministic and reasonably balanced.
    - If a question is already partially assigned, any new/unassigned answers for that question
      inherit the existing faculty assignment.
    - Unapproved segments (status=NEEDS_REVIEW) or unmapped questions are not assigned and reported.
    - Repeated runs are idempotent.
    """
    exam = db.get(Examination, payload.exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Examination not found")

    # 1. Fetch eligible faculty for this subject, deterministically ordered
    eligible_faculty = db.scalars(
        select(User)
        .join(FacultySubject, FacultySubject.faculty_id == User.id)
        .where(
            User.role == UserRole.FACULTY,
            User.is_active.is_(True),
            FacultySubject.subject_id == exam.subject_id,
        )
        .order_by(User.full_name, User.id)
    ).all()

    if not eligible_faculty:
        return {
            "assigned": 0,
            "unassigned": [],
            "skipped_faculty": [{"faculty": "None", "reason": "No faculty eligible for this subject"}],
            "message": "No eligible faculty available for subject",
        }

    eligible_ids = {f.id for f in eligible_faculty}

    # 2. Find existing question -> faculty mapping in this examination
    # (If Q1 was already assigned to Faculty A in a previous run/upload, keep Q1 -> Faculty A)
    existing_assignments = db.scalars(
        select(Assignment)
        .join(Answer, Answer.id == Assignment.answer_id)
        .join(Question, Question.id == Answer.question_id)
        .where(
            Question.examination_id == payload.exam_id,
            Assignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS, AssignmentStatus.COMPLETED]),
        )
        .order_by(Assignment.assigned_at.asc())
    ).all()

    question_faculty_map: Dict[int, str] = {}
    for a in existing_assignments:
        if a.answer and a.answer.question:
            qn = a.answer.question.question_number
            if qn not in question_faculty_map and a.faculty_id in eligible_ids:
                question_faculty_map[qn] = a.faculty_id

    # 3. Retrieve all defined questions for this exam
    exam_questions = db.scalars(
        select(Question)
        .where(Question.examination_id == payload.exam_id)
        .order_by(Question.question_number)
    ).all()

    # 4. Count questions already assigned to each faculty in this exam
    faculty_question_count: Dict[str, int] = {f.id: 0 for f in eligible_faculty}
    for qn, fid in question_faculty_map.items():
        if fid in faculty_question_count:
            faculty_question_count[fid] += 1

    # Overall system workload for tie-breaking
    faculty_overall_workload: Dict[str, int] = {}
    for f in eligible_faculty:
        load = db.scalar(
            select(func.count(Assignment.id)).where(
                Assignment.faculty_id == f.id,
                Assignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS]),
            )
        ) or 0
        faculty_overall_workload[f.id] = load

    # 5. For any question not yet mapped to a faculty member, allocate one
    for q in exam_questions:
        if q.question_number in question_faculty_map:
            continue
        # Pick eligible faculty with lowest question count in this exam,
        # then lowest overall workload, then alphabetical order
        sorted_candidates = sorted(
            eligible_faculty,
            key=lambda f: (
                faculty_question_count[f.id],
                faculty_overall_workload[f.id],
                f.full_name or "",
                f.id,
            )
        )
        chosen = sorted_candidates[0]
        question_faculty_map[q.question_number] = chosen.id
        faculty_question_count[chosen.id] += 1

    # 6. Retrieve all unassigned answers for this examination
    assigned_subquery = select(Assignment.answer_id).where(
        Assignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS, AssignmentStatus.COMPLETED])
    )
    unassigned_answers = db.scalars(
        select(Answer)
        .join(Question, Question.id == Answer.question_id)
        .where(
            Question.examination_id == payload.exam_id,
            Answer.id.not_in(assigned_subquery),
        )
        .order_by(Question.question_number, Answer.id)
    ).all()

    assigned_count = 0
    unassigned_list = []

    for ans in unassigned_answers:
        # Check segmentation review status
        if ans.status == SegmentationStatus.NEEDS_REVIEW:
            unassigned_list.append({
                "answer_id": ans.id,
                "question_number": ans.question.question_number if ans.question else 0,
                "reason": "Segmentation requires review before assignment",
            })
            continue

        qn = ans.question.question_number if ans.question else None
        target_faculty_id = question_faculty_map.get(qn) if qn is not None else None

        if not target_faculty_id:
            unassigned_list.append({
                "answer_id": ans.id,
                "question_number": qn or 0,
                "reason": "No eligible faculty available for this question",
            })
            continue

        assignment = Assignment(
            answer_id=ans.id,
            faculty_id=target_faculty_id,
            assignment_type=AssignmentType.PRIMARY,
            status=AssignmentStatus.ASSIGNED,
        )
        db.add(assignment)
        assigned_count += 1

    db.commit()
    return {
        "assigned": assigned_count,
        "unassigned": unassigned_list,
        "skipped_faculty": [],
    }


def _reassign_question_group(
    db: Session,
    question_id: str,
    target_faculty_id: str,
    current_assignment_id: Optional[str] = None,
) -> AssignmentRead:
    """
    Reassign all active assignments for a question to target_faculty_id,
    preserving question-wise faculty allocation.
    """
    question_assignments = db.scalars(
        select(Assignment)
        .join(Answer, Answer.id == Assignment.answer_id)
        .where(
            Answer.question_id == question_id,
            Assignment.status.in_(list(_ACTIVE_STATUSES)),
        )
    ).all()

    target_returned = None
    for a in question_assignments:
        if a.faculty_id == target_faculty_id:
            if current_assignment_id and a.id == current_assignment_id:
                target_returned = a
            continue

        a.status = AssignmentStatus.REASSIGNED
        new_a = Assignment(
            answer_id=a.answer_id,
            faculty_id=target_faculty_id,
            assignment_type=a.assignment_type,
            status=AssignmentStatus.ASSIGNED,
        )
        db.add(new_a)
        if current_assignment_id and a.id == current_assignment_id:
            target_returned = new_a
        elif not target_returned:
            target_returned = new_a

    db.commit()
    if target_returned:
        db.refresh(target_returned)
        return _enrich_assignment(target_returned)

    if current_assignment_id:
        existing = db.get(Assignment, current_assignment_id)
        if existing:
            return _enrich_assignment(existing)

    raise HTTPException(status_code=400, detail="No active assignments to reassign")


@router.post("/{assignment_id}/reassign", response_model=AssignmentRead)
def reassign_assignment_route(
    assignment_id: str,
    payload: ReassignPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Admin: Reassign all answers for this question in this examination to a specific
    or lowest-workload eligible faculty member (preserving question-wise allocation).
    """
    old = db.get(Assignment, assignment_id)
    if not old:
        raise HTTPException(status_code=404, detail="Assignment not found")

    answer = old.answer
    if not answer or not answer.question:
        raise HTTPException(status_code=400, detail="Cannot determine question for assignment")
    question = answer.question
    exam = question.examination
    if not exam:
        raise HTTPException(status_code=400, detail="Cannot determine examination for assignment")

    target_id = payload.faculty_id
    if not target_id:
        eligible = db.scalars(
            select(User)
            .join(FacultySubject, FacultySubject.faculty_id == User.id)
            .where(
                User.role == UserRole.FACULTY,
                User.is_active.is_(True),
                User.id != old.faculty_id,
                FacultySubject.subject_id == exam.subject_id,
            )
        ).all()
        if not eligible:
            raise HTTPException(status_code=400, detail="No alternative eligible faculty available")
        eligible.sort(key=lambda f: (
            len([a for a in f.assignments if a.status in _ACTIVE_STATUSES]),
            f.full_name or "",
            f.id,
        ))
        target_id = eligible[0].id
    else:
        _verify_faculty_eligible(db, target_id, answer)

    return _reassign_question_group(db, question.id, target_id, current_assignment_id=assignment_id)


@router.get("/{assignment_id}", response_model=AssignmentRead)
def get_assignment(
    assignment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: retrieve a single assignment by ID."""
    assignment = db.scalars(select(Assignment).where(Assignment.id == assignment_id)).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment with ID '{assignment_id}' not found",
        )
    return _enrich_assignment(assignment)


@router.put("/{assignment_id}", response_model=AssignmentRead)
def update_assignment(
    assignment_id: str,
    payload: AssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Admin: update an assignment's status or reassign the question group to a different faculty member.
    - To cancel: set status=CANCELLED.
    - To reassign to a different faculty: provide faculty_id (all active answers for this question
      in this examination are reassigned to preserve question-wise faculty allocation).
    """
    assignment = db.scalars(select(Assignment).where(Assignment.id == assignment_id)).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment with ID '{assignment_id}' not found",
        )

    # Handle reassignment to a different faculty (question-wise)
    if payload.faculty_id and payload.faculty_id != assignment.faculty_id:
        answer = assignment.answer
        _verify_faculty_eligible(db, payload.faculty_id, answer)
        question = answer.question if answer else None
        if not question:
            raise HTTPException(status_code=400, detail="Cannot determine question for assignment")
        return _reassign_question_group(db, question.id, payload.faculty_id, current_assignment_id=assignment_id)

    # Handle status update only
    if payload.status:
        if assignment.status == AssignmentStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change status of a COMPLETED assignment",
            )
        assignment.status = payload.status
        db.commit()
        db.refresh(assignment)

    return _enrich_assignment(assignment)


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_assignment(
    assignment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: cancel (soft-delete) an assignment by marking it CANCELLED."""
    assignment = db.scalars(select(Assignment).where(Assignment.id == assignment_id)).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment with ID '{assignment_id}' not found",
        )
    if assignment.status == AssignmentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a COMPLETED assignment",
        )
    assignment.status = AssignmentStatus.CANCELLED
    db.commit()
    return None


# ---------------------------------------------------------------------------
# FACULTY ENDPOINTS — /assignments/me/*
# ---------------------------------------------------------------------------

@router.get("/me/list", response_model=List[AssignmentRead])
def list_my_assignments(
    assignment_status: Optional[AssignmentStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
):
    """Faculty: list my own assignments (cannot see others')."""
    query = select(Assignment).where(Assignment.faculty_id == current_user.id)
    if assignment_status:
        query = query.where(Assignment.status == assignment_status)
    query = query.order_by(Assignment.assigned_at.desc())
    assignments = db.scalars(query).all()
    return [_enrich_assignment(a) for a in assignments]


@router.get("/me/{assignment_id}", response_model=AssignmentRead)
def get_my_assignment(
    assignment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
):
    """Faculty: retrieve one of my own assignments. Returns 404 if it belongs to another faculty."""
    assignment = db.scalars(
        select(Assignment).where(
            and_(
                Assignment.id == assignment_id,
                Assignment.faculty_id == current_user.id,
            )
        )
    ).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment with ID '{assignment_id}' not found",
        )
    return _enrich_assignment(assignment)
