from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import require_roles
from app.models.user import User, UserRole
from app.models.subject import Subject
from app.models.examination import Examination, ExamStatus
from app.schemas.examination import ExaminationCreate, ExaminationUpdate, ExaminationRead

router = APIRouter(prefix="/examinations", tags=["Examinations"])


@router.post("/", response_model=ExaminationRead, status_code=status.HTTP_201_CREATED)
def create_examination(
    payload: ExaminationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> ExaminationRead:
    """Create a new examination (Admin only)."""
    subject = db.get(Subject, payload.subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID '{payload.subject_id}' not found.",
        )

    # Check for duplicate examination instance
    stmt = select(Examination).where(
        Examination.subject_id == payload.subject_id,
        Examination.name == payload.name.strip(),
        Examination.academic_year == payload.academic_year.strip(),
        Examination.semester == payload.semester.strip(),
    )
    if db.scalars(stmt).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Examination '{payload.name}' for {payload.academic_year} {payload.semester} already exists for subject '{subject.code}'.",
        )

    exam = Examination(
        subject_id=payload.subject_id,
        name=payload.name.strip(),
        academic_year=payload.academic_year.strip(),
        semester=payload.semester.strip(),
        exam_date=payload.exam_date,
        total_marks=payload.total_marks,
        status=payload.status,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    return ExaminationRead(
        id=exam.id,
        subject_id=exam.subject_id,
        name=exam.name,
        academic_year=exam.academic_year,
        semester=exam.semester,
        exam_date=exam.exam_date,
        total_marks=exam.total_marks,
        status=exam.status,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
        subject_name=subject.name,
        subject_code=subject.code,
    )


@router.get("/", response_model=List[ExaminationRead])
def list_examinations(
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    status_filter: Optional[ExamStatus] = Query(None, alias="status", description="Filter by exam status"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
) -> List[ExaminationRead]:
    """List all examinations with optional filters (Admin and Faculty)."""
    stmt = select(Examination, Subject).join(
        Subject, Examination.subject_id == Subject.id
    ).order_by(Examination.created_at.desc())

    if subject_id:
        stmt = stmt.where(Examination.subject_id == subject_id)
    if status_filter:
        stmt = stmt.where(Examination.status == status_filter)
    if academic_year:
        stmt = stmt.where(Examination.academic_year == academic_year.strip())

    stmt = stmt.offset(skip).limit(limit)
    results = db.execute(stmt).all()

    output: List[ExaminationRead] = []
    for exam, subj in results:
        output.append(
            ExaminationRead(
                id=exam.id,
                subject_id=exam.subject_id,
                name=exam.name,
                academic_year=exam.academic_year,
                semester=exam.semester,
                exam_date=exam.exam_date,
                total_marks=exam.total_marks,
                status=exam.status,
                created_at=exam.created_at,
                updated_at=exam.updated_at,
                subject_name=subj.name,
                subject_code=subj.code,
            )
        )
    return output


@router.get("/{examination_id}", response_model=ExaminationRead)
def get_examination(
    examination_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
) -> ExaminationRead:
    """Get examination details by ID (Admin and Faculty)."""
    stmt = select(Examination, Subject).join(
        Subject, Examination.subject_id == Subject.id
    ).where(Examination.id == examination_id)
    result = db.execute(stmt).first()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Examination with ID '{examination_id}' not found.",
        )
    exam, subj = result
    return ExaminationRead(
        id=exam.id,
        subject_id=exam.subject_id,
        name=exam.name,
        academic_year=exam.academic_year,
        semester=exam.semester,
        exam_date=exam.exam_date,
        total_marks=exam.total_marks,
        status=exam.status,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
        subject_name=subj.name,
        subject_code=subj.code,
    )


@router.put("/{examination_id}", response_model=ExaminationRead)
def update_examination(
    examination_id: str,
    payload: ExaminationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> ExaminationRead:
    """Update examination configuration or status (Admin only)."""
    stmt = select(Examination, Subject).join(
        Subject, Examination.subject_id == Subject.id
    ).where(Examination.id == examination_id)
    result = db.execute(stmt).first()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Examination with ID '{examination_id}' not found.",
        )
    exam, subj = result

    if payload.name is not None:
        exam.name = payload.name.strip()
    if payload.academic_year is not None:
        exam.academic_year = payload.academic_year.strip()
    if payload.semester is not None:
        exam.semester = payload.semester.strip()
    if payload.exam_date is not None:
        exam.exam_date = payload.exam_date
    if payload.total_marks is not None:
        exam.total_marks = payload.total_marks
    if payload.status is not None:
        exam.status = payload.status

    db.commit()
    db.refresh(exam)

    return ExaminationRead(
        id=exam.id,
        subject_id=exam.subject_id,
        name=exam.name,
        academic_year=exam.academic_year,
        semester=exam.semester,
        exam_date=exam.exam_date,
        total_marks=exam.total_marks,
        status=exam.status,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
        subject_name=subj.name,
        subject_code=subj.code,
    )


@router.delete("/{examination_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_examination(
    examination_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Delete examination and cascade to its questions (Admin only)."""
    exam = db.get(Examination, examination_id)
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Examination with ID '{examination_id}' not found.",
        )
    db.delete(exam)
    db.commit()
    return None
