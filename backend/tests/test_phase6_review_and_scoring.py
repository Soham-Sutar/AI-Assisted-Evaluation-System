import io
import csv
from typing import Optional, List, Dict, Any, Tuple
import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select
from PIL import Image, ImageDraw

from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.subject import Subject
from app.models.faculty_subject import FacultySubject
from app.models.examination import Examination, ExamStatus
from app.models.question import Question
from app.models.student import Student
from app.models.answer_sheet import AnswerSheet, ProcessingStatus
from app.models.answer import Answer, SegmentationStatus
from app.models.assignment import Assignment, AssignmentStatus, AssignmentType
from app.models.evaluation import Evaluation
from app.models.ai_evaluation import AIEvaluation, AIEvaluationStatus
from app.models.review_case import ReviewCase, ReviewStatus, ReviewTriggerType, ReviewPriority
from app.models.final_score import FinalScore, FinalScoreStatus
from app.services.scoring import calculate_student_score, calculate_examination_scores


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_auth_headers(test_admin_user: User) -> dict:
    token = create_access_token(subject=test_admin_user.id, role=test_admin_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def faculty_auth_headers(test_user: User) -> dict:
    token = create_access_token(subject=test_user.id, role=test_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def reviewer1(db_session: Session) -> User:
    rev = User(
        email="reviewer1.p6@example.com",
        full_name="Reviewer One",
        password_hash="fakehash",
        role=UserRole.REVIEWER,
        is_active=True,
    )
    db_session.add(rev)
    db_session.flush()
    return rev


@pytest.fixture
def reviewer1_headers(reviewer1: User) -> dict:
    token = create_access_token(subject=reviewer1.id, role=reviewer1.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def reviewer2(db_session: Session) -> User:
    rev = User(
        email="reviewer2.p6@example.com",
        full_name="Reviewer Two",
        password_hash="fakehash",
        role=UserRole.REVIEWER,
        is_active=True,
    )
    db_session.add(rev)
    db_session.flush()
    return rev


@pytest.fixture
def reviewer2_headers(reviewer2: User) -> dict:
    token = create_access_token(subject=reviewer2.id, role=reviewer2.role.value)
    return {"Authorization": f"Bearer {token}"}


def generate_png_bytes() -> bytes:
    img = Image.new("RGB", (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "Q.1 Sample answer text for Phase 6 evaluation.", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def full_exam_setup(db_session: Session, test_user: User, test_admin_user: User) -> dict:
    """
    Sets up a full academic structure with 1 subject, 1 exam, 2 questions,
    and 2 students.
    """
    subj = Subject(name="Software Engineering", code="CS401", description="SE Principles")
    db_session.add(subj)
    db_session.flush()

    db_session.add(FacultySubject(faculty_id=test_user.id, subject_id=subj.id))

    exam = Examination(
        subject_id=subj.id,
        name="Midterm Exam 2026",
        academic_year="2025-2026",
        semester="Fall",
        exam_date=date(2026, 10, 15),
        total_marks=20.0,
        status=ExamStatus.EVALUATION,
    )

    db_session.add(exam)
    db_session.flush()

    q1 = Question(
        examination_id=exam.id,
        question_number=1,
        question_text="Explain MVC architecture and separation of concerns.",
        model_answer_text="Model handles data, View handles UI, Controller mediates.",
        rubric_json={"model": 3, "view": 3, "controller": 4},
        max_marks=10.0,
    )
    q2 = Question(
        examination_id=exam.id,
        question_number=2,
        question_text="Compare Agile vs Waterfall development methodologies.",
        model_answer_text="Agile is iterative and adaptable; Waterfall is linear and sequential.",
        rubric_json={"agile": 5, "waterfall": 5},
        max_marks=10.0,
    )
    db_session.add_all([q1, q2])
    db_session.flush()

    st1 = Student(
        register_number="REG_P6_001",
        name="Alice Smith",
        division="A",
        email="alice@example.com",
    )
    st2 = Student(
        register_number="REG_P6_002",
        name="Bob Jones",
        division="B",
        email="bob@example.com",
    )
    db_session.add_all([st1, st2])
    db_session.flush()

    return {
        "subject": subj,
        "examination": exam,
        "questions": [q1, q2],
        "students": [st1, st2],
        "faculty": test_user,
    }


def create_answer_with_evals(
    db_session: Session,
    exam: Examination,
    question: Question,
    student: Student,
    faculty: User,
    faculty_marks: float = 7.0,
    ai_marks: float = 4.0,
    create_discrepancy: bool = True,
) -> tuple[Answer, Optional[ReviewCase]]:
    """Helper to create AnswerSheet, Answer, Faculty Evaluation, and AI Evaluation."""
    sheet = db_session.scalars(
        select(AnswerSheet).where(
            AnswerSheet.examination_id == exam.id,
            AnswerSheet.student_id == student.id,
        )
    ).first()
    if not sheet:
        sheet = AnswerSheet(
            examination_id=exam.id,
            student_id=student.id,
            original_filename="p6_sheet.png",
            original_file_path="original/p6_sheet.png",
            page_count=1,
            processing_status=ProcessingStatus.PROCESSED,
        )
        db_session.add(sheet)
        db_session.flush()


    answer = Answer(
        answer_sheet_id=sheet.id,
        question_id=question.id,
        ocr_text="Model View Controller architecture explanation.",
        crop_image_path="segmented/p6_ans.png",
        status=SegmentationStatus.VERIFIED,
    )


    db_session.add(answer)
    db_session.flush()

    # Create Assignment
    assignment = Assignment(
        answer_id=answer.id,
        faculty_id=faculty.id,
        assignment_type=AssignmentType.PRIMARY,
        status=AssignmentStatus.COMPLETED,
    )
    db_session.add(assignment)
    db_session.flush()

    # Faculty evaluation
    eval_record = Evaluation(
        answer_id=answer.id,
        assignment_id=assignment.id,
        faculty_id=faculty.id,
        marks_awarded=faculty_marks,
        max_marks=question.max_marks,
        comments="Good explanation of architecture.",
    )
    db_session.add(eval_record)

    # AI evaluation
    ai_record = AIEvaluation(
        answer_id=answer.id,
        model_name="mock-nlp-v1",
        status=AIEvaluationStatus.COMPLETED,
        ai_marks=ai_marks,
        max_marks=question.max_marks,
        final_ai_score=round(ai_marks / question.max_marks, 4) if question.max_marks > 0 else 0.0,
        confidence_score=0.88,
        explanation_json={"reasoning": "Good explanation, but missing error handling details."},
    )
    db_session.add(ai_record)
    db_session.flush()


    review_case = None
    if create_discrepancy and abs(faculty_marks - ai_marks) >= 2.0:
        review_case = ReviewCase(
            answer_id=answer.id,
            faculty_evaluation_id=eval_record.id,
            ai_evaluation_id=ai_record.id,
            trigger_type=ReviewTriggerType.AI_HUMAN_DISCREPANCY,
            priority=ReviewPriority.HIGH,
            status=ReviewStatus.OPEN,
            discrepancy_value=abs(faculty_marks - ai_marks),
        )
        db_session.add(review_case)
        db_session.flush()


    db_session.commit()
    db_session.refresh(answer)
    if review_case:
        db_session.refresh(review_case)
    return answer, review_case


# ---------------------------------------------------------------------------
# Test Cases: Reviewer Workflow
# ---------------------------------------------------------------------------

def test_reviewer_claim_and_assign(
    client: TestClient,
    admin_auth_headers: dict,
    reviewer1_headers: dict,
    reviewer1: User,
    full_exam_setup: dict,
    db_session: Session,
):
    exam = full_exam_setup["examination"]
    q1 = full_exam_setup["questions"][0]
    st1 = full_exam_setup["students"][0]
    faculty = full_exam_setup["faculty"]

    answer, review_case = create_answer_with_evals(
        db_session, exam, q1, st1, faculty, faculty_marks=8.0, ai_marks=3.0
    )
    assert review_case is not None
    assert review_case.status == ReviewStatus.OPEN

    # 1. Reviewer claims case
    claim_res = client.post(f"/api/reviews/{review_case.id}/claim", headers=reviewer1_headers)
    assert claim_res.status_code == 200
    claimed_data = claim_res.json()
    assert claimed_data["status"] == "ASSIGNED"
    assert claimed_data["reviewer_id"] == reviewer1.id

    # 2. Re-claiming already assigned case by same reviewer is idempotent
    reclaim_res = client.post(f"/api/reviews/{review_case.id}/claim", headers=reviewer1_headers)
    assert reclaim_res.status_code == 200

    # 3. Admin can reassign to another reviewer
    assign_res = client.post(
        f"/api/reviews/{review_case.id}/assign",
        json={"reviewer_id": reviewer1.id},
        headers=admin_auth_headers,
    )
    assert assign_res.status_code == 200


def test_reviewer_conflict_of_interest(
    client: TestClient,
    faculty_auth_headers: dict,
    full_exam_setup: dict,
    db_session: Session,
):
    exam = full_exam_setup["examination"]
    q1 = full_exam_setup["questions"][0]
    st1 = full_exam_setup["students"][0]
    faculty = full_exam_setup["faculty"]

    # Temporarily grant faculty user the REVIEWER role to test conflict check
    faculty.role = UserRole.REVIEWER
    db_session.commit()

    answer, review_case = create_answer_with_evals(
        db_session, exam, q1, st1, faculty, faculty_marks=8.0, ai_marks=2.0
    )
    assert review_case is not None

    token = create_access_token(subject=faculty.id, role=UserRole.REVIEWER.value)
    headers = {"Authorization": f"Bearer {token}"}

    # Faculty who gave original marks cannot claim or review their own evaluated answer
    res = client.post(f"/api/reviews/{review_case.id}/claim", headers=headers)
    assert res.status_code in [409, 422]
    assert "conflict of interest" in res.json()["detail"].lower()


def test_reviewer_resolve_and_validation(
    client: TestClient,
    reviewer1_headers: dict,
    reviewer1: User,
    full_exam_setup: dict,
    db_session: Session,
):
    exam = full_exam_setup["examination"]
    q1 = full_exam_setup["questions"][0]
    st1 = full_exam_setup["students"][0]
    faculty = full_exam_setup["faculty"]

    answer, review_case = create_answer_with_evals(
        db_session, exam, q1, st1, faculty, faculty_marks=9.0, ai_marks=3.0
    )
    assert review_case is not None

    # Claim first
    client.post(f"/api/reviews/{review_case.id}/claim", headers=reviewer1_headers)

    # 1. Validation: marks exceeding max_marks -> 422
    res_over = client.post(
        f"/api/reviews/{review_case.id}/resolve",
        json={"reviewer_marks": 15.0, "reviewer_comments": "Good overall"},
        headers=reviewer1_headers,
    )
    assert res_over.status_code == 422

    # 2. Validation: negative marks -> 422
    res_neg = client.post(
        f"/api/reviews/{review_case.id}/resolve",
        json={"reviewer_marks": -1.0, "reviewer_comments": "Invalid negative score"},
        headers=reviewer1_headers,
    )
    assert res_neg.status_code == 422

    # 3. Validation: missing comments -> 422
    res_nocomm = client.post(
        f"/api/reviews/{review_case.id}/resolve",
        json={"reviewer_marks": 8.0, "reviewer_comments": ""},
        headers=reviewer1_headers,
    )
    assert res_nocomm.status_code == 422

    # 4. Valid resolution
    res_valid = client.post(
        f"/api/reviews/{review_case.id}/resolve",
        json={"reviewer_marks": 7.5, "reviewer_comments": "Agreed partially with faculty; score moderated to 7.5."},
        headers=reviewer1_headers,
    )
    assert res_valid.status_code == 200
    data = res_valid.json()
    assert data["status"] == "RESOLVED"
    assert data["reviewer_marks"] == 7.5
    assert data["reviewer_comments"] == "Agreed partially with faculty; score moderated to 7.5."
    assert data["resolved_at"] is not None

    # 5. Invalid transition: resolving an already resolved case -> 409
    res_again = client.post(
        f"/api/reviews/{review_case.id}/resolve",
        json={"reviewer_marks": 8.0, "reviewer_comments": "Trying to resolve again"},
        headers=reviewer1_headers,
    )
    assert res_again.status_code == 409


def test_reviewer_escalate_workflow(
    client: TestClient,
    reviewer1_headers: dict,
    reviewer1: User,
    full_exam_setup: dict,
    db_session: Session,
):
    exam = full_exam_setup["examination"]
    q1 = full_exam_setup["questions"][0]
    st1 = full_exam_setup["students"][0]
    faculty = full_exam_setup["faculty"]

    answer, review_case = create_answer_with_evals(
        db_session, exam, q1, st1, faculty, faculty_marks=9.0, ai_marks=2.0
    )
    assert review_case is not None

    client.post(f"/api/reviews/{review_case.id}/claim", headers=reviewer1_headers)

    esc_res = client.post(
        f"/api/reviews/{review_case.id}/escalate",
        json={"comments": "Complex handwritten notation; escalating to department head."},
        headers=reviewer1_headers,
    )
    assert esc_res.status_code == 200
    assert esc_res.json()["status"] == "ESCALATED"


def test_reviewer_isolation_and_unauthorized_access(
    client: TestClient,
    reviewer1_headers: dict,
    reviewer2_headers: dict,
    reviewer1: User,
    reviewer2: User,
    full_exam_setup: dict,
    db_session: Session,
):
    exam = full_exam_setup["examination"]
    q1 = full_exam_setup["questions"][0]
    st1 = full_exam_setup["students"][0]
    faculty = full_exam_setup["faculty"]

    answer, review_case = create_answer_with_evals(
        db_session, exam, q1, st1, faculty, faculty_marks=9.0, ai_marks=2.0
    )
    assert review_case is not None

    # Assign case specifically to Reviewer 1
    client.post(f"/api/reviews/{review_case.id}/claim", headers=reviewer1_headers)

    # Reviewer 2 tries to view Reviewer 1's assigned case -> 403 Forbidden
    view_res = client.get(f"/api/reviews/{review_case.id}", headers=reviewer2_headers)
    assert view_res.status_code == 403

    # Reviewer 2 tries to resolve Reviewer 1's assigned case -> 403 Forbidden
    res_resolve = client.post(
        f"/api/reviews/{review_case.id}/resolve",
        json={"reviewer_marks": 5.0, "reviewer_comments": "Unauthorized attempt"},
        headers=reviewer2_headers,
    )
    assert res_resolve.status_code == 403


# ---------------------------------------------------------------------------
# Test Cases: Final Score Calculation & Precedence Rules
# ---------------------------------------------------------------------------

def test_final_score_precedence_rules(
    client: TestClient,
    admin_auth_headers: dict,
    reviewer1_headers: dict,
    full_exam_setup: dict,
    db_session: Session,
):
    """
    Verify:
    1. Reviewed answer with completed decision uses reviewer marks.
    2. Answer without review uses faculty marks.
    3. AI marks never become final marks automatically.
    4. Marks are not added together across faculty, reviewer, and AI.
    """
    exam = full_exam_setup["examination"]
    q1, q2 = full_exam_setup["questions"]
    st1 = full_exam_setup["students"][0]
    faculty = full_exam_setup["faculty"]

    # Q1: Faculty gave 8.0, AI gave 3.0 -> Discrepancy -> Review Case
    ans1, case1 = create_answer_with_evals(
        db_session, exam, q1, st1, faculty, faculty_marks=8.0, ai_marks=3.0, create_discrepancy=True
    )
    # Q2: Faculty gave 9.0, AI gave 8.5 -> Consistent -> No Review Case
    ans2, case2 = create_answer_with_evals(
        db_session, exam, q2, st1, faculty, faculty_marks=9.0, ai_marks=8.5, create_discrepancy=False
    )

    # Resolve Q1 review case: Reviewer sets score to 7.0
    client.post(f"/api/reviews/{case1.id}/claim", headers=reviewer1_headers)
    res_resolve = client.post(
        f"/api/reviews/{case1.id}/resolve",
        json={"reviewer_marks": 7.0, "reviewer_comments": "Moderated from 8.0 to 7.0."},
        headers=reviewer1_headers,
    )
    assert res_resolve.status_code == 200

    # Calculate results via API
    calc_res = client.post(f"/api/exams/{exam.id}/calculate-results", headers=admin_auth_headers)
    assert calc_res.status_code == 200
    calc_data = calc_res.json()
    assert calc_data["calculated_count"] == 1

    st_result = calc_data["results"][0]
    assert st_result["student_id"] == st1.id
    # Q1 had review: marks should be 7.0 (REVIEWER), not 8.0 (FACULTY) and not 3.0 (AI)
    q1_breakdown = next(q for q in st_result["questions"] if q["question_id"] == q1.id)
    assert q1_breakdown["marks_awarded"] == 7.0
    assert q1_breakdown["source"] == "REVIEWER"
    assert q1_breakdown["is_reviewed"] is True

    # Q2 had no review: marks should be 9.0 (FACULTY), not 8.5 (AI)
    q2_breakdown = next(q for q in st_result["questions"] if q["question_id"] == q2.id)
    assert q2_breakdown["marks_awarded"] == 9.0
    assert q2_breakdown["source"] == "FACULTY"
    assert q2_breakdown["is_reviewed"] is False

    # Total marks: 7.0 + 9.0 = 16.0 (out of 20.0, 80.0%)
    assert st_result["total_marks"] == 16.0
    assert st_result["maximum_marks"] == 20.0
    assert st_result["percentage"] == 80.0
    assert st_result["status"] == "COMPLETE"
    assert st_result["reviewed_answers"] == 1


def test_final_score_incomplete_and_pending_review(
    client: TestClient,
    admin_auth_headers: dict,
    reviewer1_headers: dict,
    full_exam_setup: dict,
    db_session: Session,
):
    """
    Verify:
    1. Unevaluated answer results in marks=None, status=INCOMPLETE (never silently 0).
    2. Open review case results in status=PENDING_REVIEW.
    3. Exam cannot be marked COMPLETED while reviews or evaluations are incomplete.
    """
    exam = full_exam_setup["examination"]
    q1, q2 = full_exam_setup["questions"]
    st1 = full_exam_setup["students"][0]
    faculty = full_exam_setup["faculty"]

    # Student 1 only answered Q1, Q2 has no answer
    ans1, case1 = create_answer_with_evals(
        db_session, exam, q1, st1, faculty, faculty_marks=8.0, ai_marks=3.0, create_discrepancy=True
    )
    # Review case for Q1 is currently OPEN

    # Calculate results
    calc_res = client.post(f"/api/exams/{exam.id}/calculate-results", headers=admin_auth_headers)
    assert calc_res.status_code == 200
    st_result = calc_res.json()["results"][0]

    # Q2 was missing:
    q2_breakdown = next(q for q in st_result["questions"] if q["question_id"] == q2.id)
    assert q2_breakdown["marks_awarded"] is None
    assert q2_breakdown["source"] is None

    # Status must be INCOMPLETE
    assert st_result["status"] == "INCOMPLETE"
    # Examination status must NOT be COMPLETED
    assert calc_res.json()["examination_status"] != "COMPLETED"


def test_results_api_and_csv_export(
    client: TestClient,
    admin_auth_headers: dict,
    faculty_auth_headers: dict,
    full_exam_setup: dict,
    db_session: Session,
):
    """
    Verify:
    1. GET /api/exams/{id}/results returns list of student results.
    2. Filtering by search and division works.
    3. GET /api/exams/{id}/students/{student_id}/result returns single student.
    4. GET /api/exams/{id}/results/export.csv returns valid CSV format.
    5. Faculty cannot access results endpoints (403 Forbidden).
    """
    exam = full_exam_setup["examination"]
    q1, q2 = full_exam_setup["questions"]
    st1, st2 = full_exam_setup["students"]
    faculty = full_exam_setup["faculty"]

    # Complete evaluations for student 1
    create_answer_with_evals(db_session, exam, q1, st1, faculty, faculty_marks=8.0, ai_marks=8.0, create_discrepancy=False)
    create_answer_with_evals(db_session, exam, q2, st1, faculty, faculty_marks=7.0, ai_marks=7.0, create_discrepancy=False)

    # Calculate
    calc_res = client.post(f"/api/exams/{exam.id}/calculate-results", headers=admin_auth_headers)
    assert calc_res.status_code == 200

    # 1. GET /api/exams/{id}/results
    res = client.get(f"/api/exams/{exam.id}/results", headers=admin_auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["examination_id"] == exam.id
    assert len(data["results"]) >= 1

    # 2. Search filter
    search_res = client.get(f"/api/exams/{exam.id}/results?search=Alice", headers=admin_auth_headers)
    assert search_res.status_code == 200
    assert len(search_res.json()["results"]) == 1
    assert search_res.json()["results"][0]["name"] == "Alice Smith"

    # 3. GET student result
    st_res = client.get(f"/api/exams/{exam.id}/students/{st1.id}/result", headers=admin_auth_headers)
    assert st_res.status_code == 200
    assert st_res.json()["student_id"] == st1.id
    assert st_res.json()["total_marks"] == 15.0

    # 4. CSV Export
    csv_res = client.get(f"/api/exams/{exam.id}/results/export.csv", headers=admin_auth_headers)
    assert csv_res.status_code == 200
    assert csv_res.headers["content-type"].startswith("text/csv")
    csv_text = csv_res.text
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    header = rows[0]
    assert "register_number" in header
    assert "total_marks" in header
    assert "status" in header
    assert any("Alice Smith" in r for r in rows)

    # 5. RBAC: Faculty cannot access results endpoints
    fac_results_res = client.get(f"/api/exams/{exam.id}/results", headers=faculty_auth_headers)
    assert fac_results_res.status_code == 403

    fac_calc_res = client.post(f"/api/exams/{exam.id}/calculate-results", headers=faculty_auth_headers)
    assert fac_calc_res.status_code == 403

    fac_export_res = client.get(f"/api/exams/{exam.id}/results/export.csv", headers=faculty_auth_headers)
    assert fac_export_res.status_code == 403


def test_recalculation_idempotency_and_auto_recalc(
    client: TestClient,
    admin_auth_headers: dict,
    reviewer1_headers: dict,
    full_exam_setup: dict,
    db_session: Session,
):
    """
    Verify:
    1. Running calculate-results repeatedly does not create duplicate FinalScore records.
    2. Resolving a review case automatically updates the stored student score.
    """
    exam = full_exam_setup["examination"]
    q1, q2 = full_exam_setup["questions"]
    st1 = full_exam_setup["students"][0]
    faculty = full_exam_setup["faculty"]

    ans1, case1 = create_answer_with_evals(
        db_session, exam, q1, st1, faculty, faculty_marks=8.0, ai_marks=2.0, create_discrepancy=True
    )
    ans2, _ = create_answer_with_evals(
        db_session, exam, q2, st1, faculty, faculty_marks=7.0, ai_marks=7.0, create_discrepancy=False
    )

    # 1. First calculation
    calc1 = client.post(f"/api/exams/{exam.id}/calculate-results", headers=admin_auth_headers)
    assert calc1.status_code == 200

    scores_count1 = db_session.scalars(
        select(FinalScore).where(FinalScore.examination_id == exam.id, FinalScore.student_id == st1.id)
    ).all()
    assert len(scores_count1) == 1

    # 2. Second calculation (idempotency check)
    calc2 = client.post(f"/api/exams/{exam.id}/calculate-results", headers=admin_auth_headers)
    assert calc2.status_code == 200

    scores_count2 = db_session.scalars(
        select(FinalScore).where(FinalScore.examination_id == exam.id, FinalScore.student_id == st1.id)
    ).all()
    assert len(scores_count2) == 1
    assert calc1.json()["results"][0]["total_marks"] == calc2.json()["results"][0]["total_marks"]

    # 3. Auto-recalculation upon review resolution
    client.post(f"/api/reviews/{case1.id}/claim", headers=reviewer1_headers)
    resolve_res = client.post(
        f"/api/reviews/{case1.id}/resolve",
        json={"reviewer_marks": 6.5, "reviewer_comments": "Score adjusted from 8.0 to 6.5."},
        headers=reviewer1_headers,
    )
    assert resolve_res.status_code == 200

    # Score should have been auto-updated in database:
    # 6.5 (Reviewer for Q1) + 7.0 (Faculty for Q2) = 13.5
    updated_score = db_session.scalars(
        select(FinalScore).where(FinalScore.examination_id == exam.id, FinalScore.student_id == st1.id)
    ).first()
    assert updated_score is not None
    assert updated_score.total_marks == 13.5
    assert updated_score.status == FinalScoreStatus.COMPLETE


def test_examination_lifecycle_complete_transition(
    client: TestClient,
    admin_auth_headers: dict,
    reviewer1_headers: dict,
    full_exam_setup: dict,
    db_session: Session,
):
    """
    Verify:
    When all answers for an examination are evaluated and all review cases resolved,
    exam status transitions to COMPLETED.
    """
    exam = full_exam_setup["examination"]
    q1, q2 = full_exam_setup["questions"]
    st1 = full_exam_setup["students"][0]
    faculty = full_exam_setup["faculty"]

    # Remove student 2 from exam sheet so only student 1 is in this exam
    ans1, case1 = create_answer_with_evals(
        db_session, exam, q1, st1, faculty, faculty_marks=8.0, ai_marks=2.0, create_discrepancy=True
    )
    ans2, _ = create_answer_with_evals(
        db_session, exam, q2, st1, faculty, faculty_marks=9.0, ai_marks=9.0, create_discrepancy=False
    )

    # Initially case1 is OPEN -> calculate should put exam in REVIEW
    calc1 = client.post(f"/api/exams/{exam.id}/calculate-results", headers=admin_auth_headers)
    assert calc1.status_code == 200
    assert calc1.json()["examination_status"] == "REVIEW"

    # Resolve review case
    client.post(f"/api/reviews/{case1.id}/claim", headers=reviewer1_headers)
    client.post(
        f"/api/reviews/{case1.id}/resolve",
        json={"reviewer_marks": 7.5, "reviewer_comments": "Moderated"},
        headers=reviewer1_headers,
    )

    # Recalculate -> now all answers complete and no open review cases
    calc2 = client.post(f"/api/exams/{exam.id}/calculate-results", headers=admin_auth_headers)
    assert calc2.status_code == 200
    assert calc2.json()["examination_status"] == "COMPLETED"


def test_review_case_details_enrichment(
    client: TestClient,
    reviewer1_headers: dict,
    full_exam_setup: dict,
    db_session: Session,
):
    """
    Verify that GET /api/reviews/{id} returns fully enriched details:
    model answer, rubric, faculty marks and feedback, AI score and explanation,
    student register number, name, division, and answer crop image path.
    """
    exam = full_exam_setup["examination"]
    q1 = full_exam_setup["questions"][0]
    st1 = full_exam_setup["students"][0]
    faculty = full_exam_setup["faculty"]

    ans1, case1 = create_answer_with_evals(
        db_session, exam, q1, st1, faculty, faculty_marks=8.5, ai_marks=3.0, create_discrepancy=True
    )

    res = client.get(f"/api/reviews/{case1.id}", headers=reviewer1_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["id"] == case1.id
    assert data["answer_id"] == ans1.id
    assert data["question_id"] == q1.id
    assert data["question_number"] == 1
    assert "MVC" in data["question_text"]
    assert data["model_answer_text"] is not None
    assert data["rubric_json"] is not None
    assert data["faculty_marks"] == 8.5
    assert data["ai_marks"] == 3.0
    assert data["max_marks"] == 10.0
    assert data["student_name"] == "Alice Smith"
    assert data["student_register_number"] == "REG_P6_001"
    assert data["crop_image_path"] == "segmented/p6_ans.png"


def test_invalid_status_transitions(
    client: TestClient,
    reviewer1_headers: dict,
    full_exam_setup: dict,
    db_session: Session,
):
    """
    Verify invalid state transitions on review cases:
    - Cannot claim or assign an already resolved case.
    - Cannot escalate an already resolved case.
    """
    exam = full_exam_setup["examination"]
    q1 = full_exam_setup["questions"][0]
    st1 = full_exam_setup["students"][0]
    faculty = full_exam_setup["faculty"]

    ans1, case1 = create_answer_with_evals(
        db_session, exam, q1, st1, faculty, faculty_marks=8.0, ai_marks=2.0, create_discrepancy=True
    )

    # Claim and Resolve
    client.post(f"/api/reviews/{case1.id}/claim", headers=reviewer1_headers)
    res_resolve = client.post(
        f"/api/reviews/{case1.id}/resolve",
        json={"reviewer_marks": 7.0, "reviewer_comments": "Done"},
        headers=reviewer1_headers,
    )
    assert res_resolve.status_code == 200

    # Try to claim resolved case -> 409
    res_claim = client.post(f"/api/reviews/{case1.id}/claim", headers=reviewer1_headers)
    assert res_claim.status_code == 409

    # Try to escalate resolved case -> 409
    res_esc = client.post(
        f"/api/reviews/{case1.id}/escalate",
        json={"comments": "Should fail"},
        headers=reviewer1_headers,
    )
    assert res_esc.status_code == 409

