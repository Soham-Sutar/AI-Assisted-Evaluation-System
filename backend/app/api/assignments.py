import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.core.database import get_db
from app.api.deps import get_current_active_user, require_roles
from app.models.user import User, UserRole
from app.models.assignment import Assignment, AssignmentStatus, AssignmentType
from app.models.answer import Answer
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

@router.post("/", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
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


@router.get("/", response_model=List[AssignmentRead])
def list_assignments(
    faculty_id: Optional[str] = Query(None, description="Filter by faculty ID"),
    answer_id: Optional[str] = Query(None, description="Filter by answer ID"),
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
    return [_enrich_assignment(a) for a in assignments]


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
    Admin: update an assignment's status or reassign it to a different faculty member.
    - To cancel: set status=CANCELLED.
    - To reassign to a different faculty: provide faculty_id (old assignment is
      marked REASSIGNED and a new ASSIGNED record is created).
    """
    assignment = db.scalars(select(Assignment).where(Assignment.id == assignment_id)).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment with ID '{assignment_id}' not found",
        )

    # Handle reassignment to a different faculty
    if payload.faculty_id and payload.faculty_id != assignment.faculty_id:
        answer = assignment.answer
        _verify_faculty_eligible(db, payload.faculty_id, answer)

        # Prevent duplicate active assignments for the new faculty
        duplicate = db.scalars(
            select(Assignment).where(
                and_(
                    Assignment.answer_id == assignment.answer_id,
                    Assignment.faculty_id == payload.faculty_id,
                    Assignment.assignment_type == assignment.assignment_type,
                    Assignment.status.in_(list(_ACTIVE_STATUSES)),
                )
            )
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Target faculty already has an active assignment for this answer (ID: {duplicate.id})",
            )

        # Mark old assignment as REASSIGNED
        assignment.status = AssignmentStatus.REASSIGNED
        db.flush()

        # Create new assignment for new faculty
        new_assignment = Assignment(
            answer_id=assignment.answer_id,
            faculty_id=payload.faculty_id,
            assignment_type=assignment.assignment_type,
            status=AssignmentStatus.ASSIGNED,
        )
        db.add(new_assignment)
        db.commit()
        db.refresh(new_assignment)
        logger.info(
            "Assignment %s reassigned to faculty %s → new assignment %s",
            assignment_id,
            payload.faculty_id,
            new_assignment.id,
        )
        return _enrich_assignment(new_assignment)

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
