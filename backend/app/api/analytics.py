import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_roles
from app.models.user import User, UserRole
from app.services import analytics_service

logger = logging.getLogger("evalai.api.analytics")

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview")
def overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Overview counts and faculty workload across all examinations."""
    return {
        **analytics_service.overview(db),
        "faculty_workload": analytics_service.faculty_workload(db),
    }


@router.get("/exams/{exam_id}")
def exam_analytics_endpoint(
    exam_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Examination analytics, score distribution, and evaluation pattern indicators."""
    try:
        return analytics_service.exam_analytics(db, str(exam_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/faculty/{faculty_id}")
def faculty_analytics_endpoint(
    faculty_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Evaluation summary for a specific faculty member."""
    return analytics_service.faculty_summary(db, str(faculty_id))
