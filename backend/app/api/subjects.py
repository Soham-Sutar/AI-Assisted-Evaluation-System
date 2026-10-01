from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from app.core.database import get_db
from app.api.deps import require_roles
from app.models.user import User, UserRole
from app.models.subject import Subject
from app.models.examination import Examination
from app.schemas.subject import SubjectCreate, SubjectUpdate, SubjectRead

router = APIRouter(prefix="/subjects", tags=["Subjects"])


@router.post("/", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
def create_subject(
    payload: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> SubjectRead:
    """Create a new subject (Admin only)."""
    normalized_code = payload.code.strip().upper()
    stmt = select(Subject).where(Subject.code == normalized_code)
    if db.scalars(stmt).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Subject with code '{normalized_code}' already exists.",
        )

    subject = Subject(
        name=payload.name.strip(),
        code=normalized_code,
        description=payload.description.strip() if payload.description else None,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@router.get("/", response_model=List[SubjectRead])
def list_subjects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None, description="Search by code or name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
) -> List[SubjectRead]:
    """List all academic subjects (Admin and Faculty)."""
    stmt = select(Subject).order_by(Subject.code.asc())
    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(or_(Subject.name.ilike(term), Subject.code.ilike(term)))

    stmt = stmt.offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


@router.get("/{subject_id}", response_model=SubjectRead)
def get_subject(
    subject_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
) -> SubjectRead:
    """Get subject details by ID (Admin and Faculty)."""
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID '{subject_id}' not found.",
        )
    return subject


@router.put("/{subject_id}", response_model=SubjectRead)
def update_subject(
    subject_id: str,
    payload: SubjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> SubjectRead:
    """Update subject details (Admin only)."""
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID '{subject_id}' not found.",
        )

    if payload.code is not None:
        normalized_code = payload.code.strip().upper()
        if normalized_code != subject.code:
            existing = db.scalars(select(Subject).where(Subject.code == normalized_code)).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Subject with code '{normalized_code}' already exists.",
                )
            subject.code = normalized_code

    if payload.name is not None:
        subject.name = payload.name.strip()

    if payload.description is not None:
        subject.description = payload.description.strip() if payload.description else None

    db.commit()
    db.refresh(subject)
    return subject


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    subject_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Delete subject by ID (Admin only)."""
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID '{subject_id}' not found.",
        )

    # Check for dependent examinations
    has_exams = db.scalars(select(Examination).where(Examination.subject_id == subject_id)).first()
    if has_exams:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete subject because active examinations are associated with it.",
        )

    db.delete(subject)
    db.commit()
    return None
