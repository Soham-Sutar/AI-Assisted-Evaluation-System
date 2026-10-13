import io
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_roles
from app.models.user import User, UserRole
from app.models.examination import Examination
from app.models.student import Student
from app.schemas.result import (
    StudentResultResponse,
    ExamResultsResponse,
    CalculateResultsResponse,
)
from app.services import scoring
from app.services.audit_service import log_action
from app.services.storage_service import get_storage, StorageError

logger = logging.getLogger("evalai.api.results")

router = APIRouter(tags=["Results & Final Scores"])


def _get_exam_or_404(db: Session, exam_id: str) -> Examination:
    exam = db.get(Examination, exam_id)
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Examination with ID '{exam_id}' not found",
        )
    return exam


def _get_student_or_404(db: Session, student_id: str) -> Student:
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID '{student_id}' not found",
        )
    return student


# --- Calculate Results Endpoints ---

@router.post(
    "/exams/{exam_id}/calculate-results",
    response_model=CalculateResultsResponse,
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/examinations/{exam_id}/calculate-results",
    response_model=CalculateResultsResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def calculate_exam_results(
    exam_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> CalculateResultsResponse:
    """
    Calculate and persist final scores for all students in an examination.
    
    Rules:
    - Answer with completed reviewer decision uses reviewer marks.
    - Normal evaluated answer uses faculty marks.
    - AI marks are advisory and never automatically become final marks.
    - Unevaluated/missing answers are marked INCOMPLETE (not silent zero).
    - If unresolved review cases remain, student status is PENDING_REVIEW and exam remains in REVIEW.
    """
    exam = _get_exam_or_404(db, exam_id)
    try:
        final_scores = scoring.calculate_examination_scores(
            db, examination_id=exam_id, actor_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    student_results = [
        scoring.get_student_result_response(db, examination_id=exam_id, student_id=fs.student_id)
        for fs in final_scores
    ]

    return CalculateResultsResponse(
        examination_id=exam.id,
        calculated_count=len(final_scores),
        results=student_results,
        examination_status=exam.status.value,
        message=(
            f"Successfully calculated results for {len(final_scores)} students. "
            f"Examination status is {exam.status.value}."
        ),
    )


# --- List / View Results Endpoints ---

@router.get(
    "/exams/{exam_id}/results",
    response_model=ExamResultsResponse,
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/examinations/{exam_id}/results",
    response_model=ExamResultsResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_examination_results(
    exam_id: str,
    search: Optional[str] = Query(None, description="Search by student name or register number"),
    division: Optional[str] = Query(None, description="Filter by student division"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by score status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> ExamResultsResponse:
    """
    Retrieve examination results breakdown with question summaries and statistical totals.
    Restricted to Admin and Reviewer roles.
    """
    _get_exam_or_404(db, exam_id)
    try:
        return scoring.get_examination_results_response(
            db,
            examination_id=exam_id,
            search=search,
            division=division,
            status_filter=status_filter,
            skip=skip,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/exams/{exam_id}/students/{student_id}/result",
    response_model=StudentResultResponse,
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/examinations/{exam_id}/students/{student_id}/result",
    response_model=StudentResultResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_student_exam_result(
    exam_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> StudentResultResponse:
    """
    Retrieve full question-level result breakdown for a single student in an examination.
    """
    _get_exam_or_404(db, exam_id)
    _get_student_or_404(db, student_id)
    try:
        return scoring.get_student_result_response(
            db, examination_id=exam_id, student_id=student_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Export CSV Endpoint ---

@router.get(
    "/exams/{exam_id}/results/export.csv",
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/examinations/{exam_id}/results/export.csv",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def export_exam_results_csv(
    exam_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
):
    """
    Export examination results as CSV format.
    Columns include student register number, name, division, each question score, total, max, %, status.
    """
    exam = _get_exam_or_404(db, exam_id)
    try:
        csv_content = scoring.export_examination_results_csv(db, examination_id=exam_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"results_{str(exam_id)[:8]}_{timestamp}.csv"

    try:
        storage = get_storage()
        export_dir = storage.category_dir("exports")
        (export_dir / filename).write_text(csv_content, encoding="utf-8")
    except (StorageError, Exception) as err:
        logger.warning(f"Could not save CSV export to storage root: {err}")

    log_action(
        db,
        user_id=current_user.id,
        action="results.exported",
        entity_type="Examination",
        entity_id=exam_id,
        metadata={"filename": filename},
        commit=True,
    )

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
