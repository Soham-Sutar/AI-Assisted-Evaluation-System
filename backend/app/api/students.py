from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from app.core.database import get_db
from app.api.deps import require_roles
from app.models.user import User, UserRole
from app.models.student import Student
from app.schemas.student import StudentCreate, StudentUpdate, StudentRead

router = APIRouter(prefix="/students", tags=["Students"])


@router.post("/", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> StudentRead:
    """Register a new student (Admin only)."""
    normalized_reg = payload.register_number.strip().upper()
    stmt = select(Student).where(Student.register_number == normalized_reg)
    if db.scalars(stmt).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student with register number '{normalized_reg}' already exists.",
        )

    student = Student(
        register_number=normalized_reg,
        name=payload.name.strip(),
        division=payload.division.strip() if payload.division else None,
        email=str(payload.email).strip().lower() if payload.email else None,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/", response_model=List[StudentRead])
def list_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None, description="Search by register number or name"),
    division: Optional[str] = Query(None, description="Filter by division"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
) -> List[StudentRead]:
    """List registered students with pagination and search (Admin and Faculty)."""
    stmt = select(Student).order_by(Student.register_number.asc())

    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(or_(Student.register_number.ilike(term), Student.name.ilike(term)))

    if division and division.strip():
        stmt = stmt.where(Student.division == division.strip())

    stmt = stmt.offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


@router.get("/{student_id}", response_model=StudentRead)
def get_student(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
) -> StudentRead:
    """Get student details by ID (Admin and Faculty)."""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID '{student_id}' not found.",
        )
    return student


@router.put("/{student_id}", response_model=StudentRead)
def update_student(
    student_id: str,
    payload: StudentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> StudentRead:
    """Update student record (Admin only)."""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID '{student_id}' not found.",
        )

    if payload.register_number is not None:
        normalized_reg = payload.register_number.strip().upper()
        if normalized_reg != student.register_number:
            existing = db.scalars(
                select(Student).where(Student.register_number == normalized_reg)
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Student with register number '{normalized_reg}' already exists.",
                )
            student.register_number = normalized_reg

    if payload.name is not None:
        student.name = payload.name.strip()
    if payload.division is not None:
        student.division = payload.division.strip() if payload.division else None
    if payload.email is not None:
        student.email = str(payload.email).strip().lower() if payload.email else None

    db.commit()
    db.refresh(student)
    return student


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Delete a student record (Admin only)."""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID '{student_id}' not found.",
        )
    db.delete(student)
    db.commit()
    return None
