import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import admin_only, get_db
from app.models import User
from app.services import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview")
def overview(db=Depends(get_db), _: User = Depends(admin_only)):
    return {**analytics_service.overview(db), "faculty_workload": analytics_service.faculty_workload(db)}


@router.get("/exams/{exam_id}")
def exam(exam_id: uuid.UUID, db=Depends(get_db), _: User = Depends(admin_only)):
    try:
        return analytics_service.exam_analytics(db, exam_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@router.get("/faculty/{faculty_id}")
def faculty(faculty_id: uuid.UUID, db=Depends(get_db), _: User = Depends(admin_only)):
    return analytics_service.faculty_summary(db, faculty_id)
