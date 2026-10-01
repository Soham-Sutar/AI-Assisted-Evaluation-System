from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import require_roles
from app.models.user import User, UserRole
from app.models.subject import Subject
from app.models.faculty_subject import FacultySubject
from app.schemas.faculty_subject import FacultySubjectCreate, FacultySubjectRead

router = APIRouter(prefix="/faculty-subjects", tags=["Faculty Subjects"])


@router.post("/", response_model=FacultySubjectRead, status_code=status.HTTP_201_CREATED)
def assign_faculty_to_subject(
    payload: FacultySubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> FacultySubjectRead:
    """Assign an eligible faculty member to a subject (Admin only)."""
    # Verify faculty user exists and has FACULTY role
    faculty = db.get(User, payload.faculty_id)
    if not faculty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Faculty user with ID '{payload.faculty_id}' not found.",
        )
    if faculty.role != UserRole.FACULTY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User '{faculty.email}' does not have the FACULTY role (current role: {faculty.role.value}).",
        )

    # Verify subject exists
    subject = db.get(Subject, payload.subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID '{payload.subject_id}' not found.",
        )

    # Check duplicate assignment
    stmt = select(FacultySubject).where(
        FacultySubject.faculty_id == payload.faculty_id,
        FacultySubject.subject_id == payload.subject_id,
    )
    if db.scalars(stmt).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Faculty member '{faculty.full_name}' is already assigned to subject '{subject.code}'.",
        )

    assignment = FacultySubject(
        faculty_id=payload.faculty_id,
        subject_id=payload.subject_id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return FacultySubjectRead(
        id=assignment.id,
        faculty_id=assignment.faculty_id,
        subject_id=assignment.subject_id,
        created_at=assignment.created_at,
        faculty_name=faculty.full_name,
        faculty_email=faculty.email,
        subject_name=subject.name,
        subject_code=subject.code,
    )


@router.get("/", response_model=List[FacultySubjectRead])
def list_faculty_subjects(
    faculty_id: Optional[str] = Query(None, description="Filter by faculty ID"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
) -> List[FacultySubjectRead]:
    """List faculty-subject eligibility mappings.
    
    Admins can view all mappings or filter by faculty/subject.
    Faculty can only view their own assigned subjects.
    """
    stmt = select(FacultySubject, User, Subject).join(
        User, FacultySubject.faculty_id == User.id
    ).join(
        Subject, FacultySubject.subject_id == Subject.id
    )

    if current_user.role == UserRole.FACULTY:
        # Enforce faculty sees only their own assignments
        stmt = stmt.where(FacultySubject.faculty_id == current_user.id)
    else:
        if faculty_id:
            stmt = stmt.where(FacultySubject.faculty_id == faculty_id)

    if subject_id:
        stmt = stmt.where(FacultySubject.subject_id == subject_id)

    results = db.execute(stmt).all()
    output: List[FacultySubjectRead] = []
    for fs, user, subj in results:
        output.append(
            FacultySubjectRead(
                id=fs.id,
                faculty_id=fs.faculty_id,
                subject_id=fs.subject_id,
                created_at=fs.created_at,
                faculty_name=user.full_name,
                faculty_email=user.email,
                subject_name=subj.name,
                subject_code=subj.code,
            )
        )
    return output


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_faculty_subject_assignment(
    assignment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Remove a faculty-subject eligibility mapping (Admin only)."""
    assignment = db.get(FacultySubject, assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Faculty-subject assignment with ID '{assignment_id}' not found.",
        )
    db.delete(assignment)
    db.commit()
    return None
