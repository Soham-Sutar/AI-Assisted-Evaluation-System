import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.core.database import get_db
from app.api.deps import get_current_active_user, require_roles
from app.models.user import User, UserRole
from app.models.assignment import Assignment, AssignmentStatus
from app.models.evaluation import Evaluation
from app.models.answer import Answer
from app.models.question import Question
from app.models.ai_evaluation import AIEvaluation, AIEvaluationStatus
from app.schemas.evaluation import EvaluationCreate, EvaluationRead

logger = logging.getLogger("evalai.api.evaluations")

router = APIRouter(prefix="/evaluations", tags=["Evaluations"])


def _enrich_evaluation(evaluation: Evaluation) -> EvaluationRead:
    faculty = evaluation.faculty
    answer = evaluation.answer
    question = answer.question if answer else None
    examination = question.examination if question else None
    sheet = answer.answer_sheet if answer else None
    student = sheet.student if sheet else None

    latest_ai = None
    if answer and answer.ai_evaluations:
        latest_ai = answer.ai_evaluations[0]

    return EvaluationRead(
        id=evaluation.id,
        answer_id=evaluation.answer_id,
        faculty_id=evaluation.faculty_id,
        assignment_id=evaluation.assignment_id,
        marks_awarded=evaluation.marks_awarded,
        max_marks=evaluation.max_marks,
        comments=evaluation.comments,
        submitted_at=evaluation.submitted_at,
        version=evaluation.version,
        faculty_name=faculty.full_name if faculty else None,
        question_number=question.question_number if question else None,
        examination_name=examination.name if examination else None,
        register_number=student.register_number if student else None,
        student_name=student.name if student else None,
        ai_status=latest_ai.status.value if (latest_ai and hasattr(latest_ai.status, "value")) else (latest_ai.status if latest_ai else None),
        ai_marks=latest_ai.ai_marks if latest_ai else None,
    )


@router.post("", response_model=EvaluationRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=EvaluationRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def submit_evaluation(
    payload: EvaluationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
):
    """Faculty: Submit human evaluation for an assigned answer."""
    assignment = None
    if payload.assignment_id:
        assignment = db.scalars(select(Assignment).where(Assignment.id == payload.assignment_id)).first()
    elif payload.answer_id:
        assignment = db.scalars(
            select(Assignment).where(
                Assignment.answer_id == payload.answer_id,
                Assignment.faculty_id == current_user.id,
            )
        ).first()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment not found for evaluation",
        )

    # Prevent IDOR: Faculty can only evaluate their own assignments
    if assignment.faculty_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to evaluate this assignment",
        )

    # Check assignment status
    if assignment.status not in [AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit evaluation for assignment in status '{assignment.status.value}'",
        )

    answer = assignment.answer
    question = answer.question if answer else None
    if not question:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Associated answer has no mapped question. Cannot determine maximum marks.",
        )

    max_marks = question.max_marks

    # Validate marks if submitted
    marks = payload.marks_awarded
    if payload.submit and marks is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Marks awarded cannot be empty upon submission",
        )
    marks_val = marks if marks is not None else 0.0

    if marks_val < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Marks awarded cannot be negative",
        )
    if marks_val > max_marks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Marks awarded ({marks_val}) exceed maximum marks for the question ({max_marks})",
        )

    # Check if evaluation already exists
    existing_evaluation = db.scalars(
        select(Evaluation).where(Evaluation.assignment_id == assignment.id)
    ).first()

    if existing_evaluation:
        existing_evaluation.marks_awarded = marks_val
        existing_evaluation.comments = payload.comments
        evaluation = existing_evaluation
    else:
        evaluation = Evaluation(
            answer_id=answer.id,
            faculty_id=current_user.id,
            assignment_id=assignment.id,
            marks_awarded=marks_val,
            max_marks=max_marks,
            comments=payload.comments,
        )
        db.add(evaluation)

    if payload.submit:
        assignment.status = AssignmentStatus.COMPLETED
    else:
        assignment.status = AssignmentStatus.IN_PROGRESS

    db.commit()
    db.refresh(evaluation)

    if payload.submit:
        # Trigger independent AI evaluation and discrepancy check
        try:
            from app.services.ai_evaluator import evaluate_student_answer
            evaluate_student_answer(db, answer.id)
        except Exception as e:
            logger.warning(f"AI evaluation step note: {e}")

        try:
            from app.services.discrepancy import detect_and_create_review_case
            detect_and_create_review_case(db, answer.id)
        except Exception as e:
            logger.warning(f"Discrepancy check step note: {e}")

    logger.info(
        "Evaluation processed: %s (faculty=%s assignment=%s marks=%s/%s submit=%s)",
        evaluation.id,
        current_user.id,
        assignment.id,
        evaluation.marks_awarded,
        max_marks,
        payload.submit,
    )

    return _enrich_evaluation(evaluation)


@router.get("/history", response_model=List[EvaluationRead])
def evaluation_history(
    exam_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
):
    """Admin and Reviewers: History of submitted faculty evaluations with AI reference alongside."""
    stmt = select(Evaluation).order_by(Evaluation.submitted_at.desc())
    evaluations = db.scalars(stmt).all()

    if exam_id:
        evaluations = [
            e for e in evaluations
            if e.answer and e.answer.question and e.answer.question.examination_id == exam_id
        ]

    return [_enrich_evaluation(e) for e in evaluations]


@router.get("/me/list", response_model=List[EvaluationRead])
def list_my_evaluations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
):
    """Faculty: List all submitted evaluations by the current faculty member."""
    evaluations = db.scalars(
        select(Evaluation).where(Evaluation.faculty_id == current_user.id).order_by(Evaluation.submitted_at.desc())
    ).all()
    return [_enrich_evaluation(e) for e in evaluations]


@router.get("/me/{evaluation_id}", response_model=EvaluationRead)
def get_my_evaluation(
    evaluation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FACULTY)),
):
    """Faculty: Retrieve a specific evaluation submitted by the current faculty member."""
    evaluation = db.scalars(
        select(Evaluation).where(
            and_(
                Evaluation.id == evaluation_id,
                Evaluation.faculty_id == current_user.id,
            )
        )
    ).first()

    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation with ID '{evaluation_id}' not found",
        )

    return _enrich_evaluation(evaluation)
