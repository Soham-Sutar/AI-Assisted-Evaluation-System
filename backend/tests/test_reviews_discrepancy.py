import io
import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from PIL import Image, ImageDraw

from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.subject import Subject
from app.models.faculty_subject import FacultySubject
from app.models.examination import Examination, ExamStatus
from app.models.question import Question
from app.models.student import Student
from app.models.answer import Answer, SegmentationStatus
from app.models.assignment import Assignment, AssignmentStatus, AssignmentType
from app.models.evaluation import Evaluation
from app.models.ai_evaluation import AIEvaluation, AIEvaluationStatus
from app.models.review_case import ReviewCase, ReviewStatus, ReviewTriggerType, ReviewPriority
from app.services.discrepancy import compute_discrepancy, priority_for_discrepancy


@pytest.fixture
def admin_auth_headers(test_admin_user: User) -> dict:
    token = create_access_token(subject=test_admin_user.id, role=test_admin_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def faculty_auth_headers(test_user: User) -> dict:
    token = create_access_token(subject=test_user.id, role=test_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def reviewer_auth_headers(db_session: Session) -> dict:
    rev = User(
        email="test.reviewer.5b@example.com",
        full_name="Reviewer User",
        password_hash="fakehash",
        role=UserRole.REVIEWER,
        is_active=True,
    )
    db_session.add(rev)
    db_session.flush()
    token = create_access_token(subject=rev.id, role=rev.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_faculty_auth_headers(db_session: Session) -> tuple[dict, User]:
    other = User(
        email="other.faculty.5b@example.com",
        full_name="Other Faculty 5B",
        password_hash="fakehash",
        role=UserRole.FACULTY,
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()
    token = create_access_token(subject=other.id, role=other.role.value)
    return {"Authorization": f"Bearer {token}"}, other


def generate_png_bytes() -> bytes:
    img = Image.new("RGB", (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "Q.1 Answers about database indexing and B-trees.", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def academic_setup(db_session: Session, test_user: User) -> dict:
    subject = Subject(name="Database Systems", code="CS302", description="Core DB Course")
    db_session.add(subject)
    db_session.flush()

    db_session.add(FacultySubject(faculty_id=test_user.id, subject_id=subject.id))

    examination = Examination(
        subject_id=subject.id,
        name="DB Midterm Exam 2026",
        academic_year="2025-2026",
        semester="Fall",
        exam_date=date(2026, 10, 22),
        total_marks=10.0,
        status=ExamStatus.READY,
    )
    db_session.add(examination)
    db_session.flush()

    q1 = Question(
        examination_id=examination.id,
        question_number=1,
        question_text="Explain B-Trees and indexing in databases.",
        max_marks=10.0,
        model_answer_text="B-trees are balanced search trees used in databases to optimize disk reads.",
        rubric_json={
            "points": [
                {"description": "Defines B-tree structure", "marks": 5.0},
                {"description": "Explains indexing and search speed", "marks": 5.0},
            ]
        },
    )
    db_session.add(q1)

    student1 = Student(register_number="DB2026001", name="Charlie Student", division="A", email="charlie@example.com")
    db_session.add(student1)
    db_session.flush()

    return {
        "subject": subject,
        "examination": examination,
        "question": q1,
        "student": student1,
        "faculty": test_user,
    }


@pytest.fixture
def evaluation_pair_factory(client: TestClient, admin_auth_headers: dict, academic_setup: dict, db_session: Session):
    """
    Factory fixture to create an Answer with associated Assignment, Evaluation, and AIEvaluation
    with customizable marks.
    """
    def _create_pair(faculty_marks: float = 4.0, ai_marks: float = 4.0, max_marks: float = 10.0):
        exam = academic_setup["examination"]
        import uuid as _uuid
        student = Student(
            register_number=f"STU{_uuid.uuid4().hex[:8].upper()}",
            name="Test Student",
            division="A",
            email=f"stu{_uuid.uuid4().hex[:8]}@example.com",
        )
        db_session.add(student)
        db_session.flush()

        faculty = academic_setup["faculty"]
        question = academic_setup["question"]
        question.max_marks = max_marks
        db_session.commit()

        # Upload answer sheet
        img_bytes = generate_png_bytes()
        upload_res = client.post(
            "/api/answer-sheets/",
            data={"examination_id": exam.id, "student_id": student.id},
            files={"file": ("sheet.png", img_bytes, "image/png")},
            headers=admin_auth_headers,
        )
        assert upload_res.status_code == 201
        answer_id = upload_res.json()["answers"][0]["id"]

        ans = db_session.get(Answer, answer_id)
        ans.ocr_text = "B-Trees keep data sorted and allow search in logarithmic time."
        ans.ocr_confidence = 90.0
        ans.status = SegmentationStatus.VERIFIED
        db_session.commit()

        # Create Assignment
        assignment = Assignment(
            answer_id=answer_id,
            faculty_id=faculty.id,
            assignment_type=AssignmentType.PRIMARY,
            status=AssignmentStatus.COMPLETED,
        )
        db_session.add(assignment)
        db_session.flush()

        # Create Faculty Evaluation
        faculty_eval = Evaluation(
            answer_id=answer_id,
            assignment_id=assignment.id,
            faculty_id=faculty.id,
            marks_awarded=faculty_marks,
            max_marks=max_marks,
            comments="Solid explanation.",
        )
        db_session.add(faculty_eval)
        db_session.flush()

        # Create AI Evaluation
        ai_eval = AIEvaluation(
            answer_id=answer_id,
            model_name="mock-nlp-v1",
            status=AIEvaluationStatus.COMPLETED,
            ai_marks=ai_marks,
            max_marks=max_marks,
            final_ai_score=round(ai_marks / max_marks, 4) if max_marks > 0 else 0.0,
            confidence_score=0.85,
            semantic_similarity=0.82,
            keypoint_score=0.80,
            explanation_json={"summary": "Accurate key concepts."},
        )
        db_session.add(ai_eval)
        db_session.commit()

        return {
            "answer_id": answer_id,
            "assignment_id": assignment.id,
            "faculty_evaluation_id": faculty_eval.id,
            "ai_evaluation_id": ai_eval.id,
            "faculty_id": faculty.id,
        }

    return _create_pair


# ---------------------------------------------------------------------------
# Unit tests for discrepancy calculations
# ---------------------------------------------------------------------------

def test_compute_discrepancy_unit_cases():
    # Identical marks: no discrepancy
    res = compute_discrepancy(faculty_marks=5.0, ai_marks=5.0, max_marks=10.0)
    assert not res.is_discrepant
    assert res.difference == 0.0
    assert res.normalized_difference == 0.0

    # Below absolute and relative threshold: diff=1.0 on max_marks=10.0 (10% < 20%, 1.0 < 2.0)
    res = compute_discrepancy(faculty_marks=7.0, ai_marks=6.0, max_marks=10.0)
    assert not res.is_discrepant
    assert res.difference == 1.0
    assert res.normalized_difference == 0.10

    # Exactly at absolute threshold: diff=2.0 on max_marks=20.0 (10% rel, but diff == 2.0 abs)
    res = compute_discrepancy(faculty_marks=10.0, ai_marks=8.0, max_marks=20.0)
    assert res.is_discrepant
    assert res.difference == 2.0

    # Exactly at relative threshold: diff=1.0 on max_marks=5.0 (20% rel, diff=1.0 < 2.0 abs)
    res = compute_discrepancy(faculty_marks=4.0, ai_marks=3.0, max_marks=5.0)
    assert res.is_discrepant
    assert res.difference == 1.0
    assert res.normalized_difference == 0.20

    # Above both thresholds: diff=4.0 on max_marks=10.0 (40% rel, 4.0 abs)
    res = compute_discrepancy(faculty_marks=8.0, ai_marks=4.0, max_marks=10.0)
    assert res.is_discrepant
    assert res.difference == 4.0

    # Zero scores: both 0.0
    res = compute_discrepancy(faculty_marks=0.0, ai_marks=0.0, max_marks=10.0)
    assert not res.is_discrepant
    assert res.difference == 0.0

    # Zero score vs 2.0: diff=2.0 -> flagged
    res = compute_discrepancy(faculty_marks=0.0, ai_marks=2.0, max_marks=10.0)
    assert res.is_discrepant
    assert res.difference == 2.0

    # Max marks is 0: edge case safe handling
    res = compute_discrepancy(faculty_marks=0.0, ai_marks=0.0, max_marks=0.0)
    assert not res.is_discrepant
    assert res.normalized_difference == 0.0


def test_priority_for_discrepancy_levels():
    # difference = 1.0, max_marks = 10 -> LOW
    assert priority_for_discrepancy(1.0, 10.0) == ReviewPriority.LOW
    # difference = 2.5, max_marks = 10 (25%) -> MEDIUM
    assert priority_for_discrepancy(2.5, 10.0) == ReviewPriority.MEDIUM
    # difference = 4.5, max_marks = 10 (45%) -> HIGH
    assert priority_for_discrepancy(4.5, 10.0) == ReviewPriority.HIGH
    # difference = 7.0, max_marks = 10 (70%) -> HIGH
    assert priority_for_discrepancy(7.0, 10.0) == ReviewPriority.HIGH



# ---------------------------------------------------------------------------
# API integration tests: Detection & Review Case creation
# ---------------------------------------------------------------------------

def test_detect_discrepancy_above_threshold_creates_review_case(
    client: TestClient,
    admin_auth_headers: dict,
    evaluation_pair_factory,
    db_session: Session,
):
    # Faculty = 8.0, AI = 4.0, max = 10.0 -> diff = 4.0 (flagged!)
    pair = evaluation_pair_factory(faculty_marks=8.0, ai_marks=4.0, max_marks=10.0)
    answer_id = pair["answer_id"]

    res = client.post(
        f"/api/answers/{answer_id}/discrepancy",
        headers=admin_auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["answer_id"] == answer_id
    assert data["has_discrepancy"] is True
    assert data["discrepancy_amount"] == 4.0
    assert data["relative_difference"] == 0.40
    assert data["faculty_marks"] == 8.0
    assert data["ai_marks"] == 4.0
    assert data["max_marks"] == 10.0
    assert data["review_case"] is not None

    rc = data["review_case"]
    assert rc["answer_id"] == answer_id
    assert rc["status"] == ReviewStatus.OPEN.value
    assert rc["trigger_type"] == ReviewTriggerType.AI_HUMAN_DISCREPANCY.value
    assert rc["priority"] in [ReviewPriority.HIGH.value, ReviewPriority.MEDIUM.value]
    assert rc["discrepancy_amount"] == 4.0
    assert "discrepancy" in rc["trigger_reason"].lower()

    # Verify directly in DB
    db_rc = db_session.query(ReviewCase).filter(ReviewCase.answer_id == answer_id).first()
    assert db_rc is not None
    assert db_rc.status == ReviewStatus.OPEN
    assert db_rc.discrepancy_amount == 4.0
    assert db_rc.faculty_marks == 8.0
    assert db_rc.ai_marks == 4.0


def test_detect_discrepancy_agreement_creates_no_case(
    client: TestClient,
    admin_auth_headers: dict,
    evaluation_pair_factory,
    db_session: Session,
):
    # Faculty = 7.0, AI = 6.5, max = 10.0 -> diff = 0.5 (< 2.0, < 20%)
    pair = evaluation_pair_factory(faculty_marks=7.0, ai_marks=6.5, max_marks=10.0)
    answer_id = pair["answer_id"]

    res = client.post(
        f"/api/answers/{answer_id}/discrepancy",
        headers=admin_auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["answer_id"] == answer_id
    assert data["has_discrepancy"] is False
    assert data["discrepancy_amount"] == 0.5
    assert data["review_case"] is None

    # Verify in DB: No ReviewCase created
    db_rc = db_session.query(ReviewCase).filter(ReviewCase.answer_id == answer_id).first()
    assert db_rc is None


def test_detect_discrepancy_idempotent_no_duplicate_cases(
    client: TestClient,
    admin_auth_headers: dict,
    evaluation_pair_factory,
    db_session: Session,
):
    pair = evaluation_pair_factory(faculty_marks=9.0, ai_marks=4.0, max_marks=10.0)
    answer_id = pair["answer_id"]

    # First call creates case
    res1 = client.post(f"/api/answers/{answer_id}/discrepancy", headers=admin_auth_headers)
    assert res1.status_code == 200
    case_id_1 = res1.json()["review_case"]["id"]

    # Second call returns existing case without duplicate
    res2 = client.post(f"/api/answers/{answer_id}/discrepancy", headers=admin_auth_headers)
    assert res2.status_code == 200
    case_id_2 = res2.json()["review_case"]["id"]
    assert case_id_1 == case_id_2

    # Verify in DB exactly one record exists
    count = db_session.query(ReviewCase).filter(ReviewCase.answer_id == answer_id).count()
    assert count == 1


def test_faculty_and_ai_marks_remain_unchanged(
    client: TestClient,
    admin_auth_headers: dict,
    evaluation_pair_factory,
    db_session: Session,
):
    pair = evaluation_pair_factory(faculty_marks=8.5, ai_marks=3.0, max_marks=10.0)
    answer_id = pair["answer_id"]
    faculty_eval_id = pair["faculty_evaluation_id"]
    ai_eval_id = pair["ai_evaluation_id"]

    # Run detection
    res = client.post(f"/api/answers/{answer_id}/discrepancy", headers=admin_auth_headers)
    assert res.status_code == 200

    # Ensure evaluation records have identical marks and were not modified
    db_session.expire_all()
    faculty_eval = db_session.get(Evaluation, faculty_eval_id)
    ai_eval = db_session.get(AIEvaluation, ai_eval_id)
    assert faculty_eval.marks_awarded == 8.5
    assert ai_eval.ai_marks == 3.0


# ---------------------------------------------------------------------------
# Error cases & validation
# ---------------------------------------------------------------------------

def test_detect_discrepancy_missing_evaluations(
    client: TestClient,
    admin_auth_headers: dict,
    academic_setup: dict,
    db_session: Session,
):
    exam = academic_setup["examination"]
    student = academic_setup["student"]

    # Upload answer sheet
    img_bytes = generate_png_bytes()
    upload_res = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("sheet.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    answer_id = upload_res.json()["answers"][0]["id"]

    # Case 1: Neither evaluation exists
    res = client.post(f"/api/answers/{answer_id}/discrepancy", headers=admin_auth_headers)
    assert res.status_code == 400
    assert "faculty evaluation" in res.json()["detail"].lower()

    # Case 2: Non-existent answer
    res_404 = client.post("/api/answers/999999/discrepancy", headers=admin_auth_headers)
    assert res_404.status_code == 404


def test_detect_discrepancy_failed_ai_evaluation(
    client: TestClient,
    admin_auth_headers: dict,
    evaluation_pair_factory,
    db_session: Session,
):
    pair = evaluation_pair_factory(faculty_marks=5.0, ai_marks=5.0, max_marks=10.0)
    answer_id = pair["answer_id"]
    ai_eval = db_session.get(AIEvaluation, pair["ai_evaluation_id"])
    ai_eval.status = AIEvaluationStatus.FAILED
    ai_eval.ai_marks = None
    db_session.commit()

    res = client.post(f"/api/answers/{answer_id}/discrepancy", headers=admin_auth_headers)
    assert res.status_code == 400
    assert "ai evaluation" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Retrieval & Querying (GET endpoints)
# ---------------------------------------------------------------------------

def test_get_discrepancy_for_answer(
    client: TestClient,
    admin_auth_headers: dict,
    evaluation_pair_factory,
):
    pair = evaluation_pair_factory(faculty_marks=7.0, ai_marks=3.0, max_marks=10.0)
    answer_id = pair["answer_id"]

    # Check before detection is run
    res_before = client.get(f"/api/answers/{answer_id}/discrepancy", headers=admin_auth_headers)
    assert res_before.status_code == 200
    data_before = res_before.json()
    assert data_before["review_case"] is None

    # Run detection
    client.post(f"/api/answers/{answer_id}/discrepancy", headers=admin_auth_headers)

    # Check after detection is run
    res_after = client.get(f"/api/answers/{answer_id}/discrepancy", headers=admin_auth_headers)
    assert res_after.status_code == 200
    data_after = res_after.json()
    assert data_after["has_discrepancy"] is True
    assert data_after["review_case"] is not None


def test_list_and_get_review_cases(
    client: TestClient,
    admin_auth_headers: dict,
    reviewer_auth_headers: dict,
    evaluation_pair_factory,
):
    pair1 = evaluation_pair_factory(faculty_marks=9.0, ai_marks=2.0, max_marks=10.0)
    pair2 = evaluation_pair_factory(faculty_marks=8.0, ai_marks=3.0, max_marks=10.0)

    # Create cases
    res1 = client.post(f"/api/answers/{pair1['answer_id']}/discrepancy", headers=admin_auth_headers)
    case1_id = res1.json()["review_case"]["id"]
    res2 = client.post(f"/api/answers/{pair2['answer_id']}/discrepancy", headers=admin_auth_headers)
    case2_id = res2.json()["review_case"]["id"]

    # List as reviewer
    list_res = client.get("/api/reviews?skip=0&limit=10", headers=reviewer_auth_headers)
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 2
    case_ids = [c["id"] for c in items]
    assert case1_id in case_ids
    assert case2_id in case_ids

    # Filter by status
    filter_res = client.get("/api/reviews?status=OPEN", headers=reviewer_auth_headers)
    assert filter_res.status_code == 200
    assert all(c["status"] == "OPEN" for c in filter_res.json())

    # Get single review case
    get_res = client.get(f"/api/reviews/{case1_id}", headers=reviewer_auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == case1_id
    assert get_res.json()["answer_id"] == pair1["answer_id"]

    # Non-existent review case
    not_found_res = client.get("/api/reviews/999999", headers=reviewer_auth_headers)
    assert not_found_res.status_code == 404


# ---------------------------------------------------------------------------
# RBAC & Anti-anchoring Security Tests
# ---------------------------------------------------------------------------

def test_rbac_and_anti_anchoring(
    client: TestClient,
    admin_auth_headers: dict,
    faculty_auth_headers: dict,
    other_faculty_auth_headers: tuple[dict, User],
    reviewer_auth_headers: dict,
    evaluation_pair_factory,
    academic_setup: dict,
    db_session: Session,
):
    other_headers, other_faculty = other_faculty_auth_headers
    pair = evaluation_pair_factory(faculty_marks=8.0, ai_marks=3.0, max_marks=10.0)
    answer_id = pair["answer_id"]

    # 1. Unauthenticated request -> 401
    unauth_res = client.get(f"/api/answers/{answer_id}/discrepancy")
    assert unauth_res.status_code == 401

    # 2. Faculty cannot list all review cases via /api/reviews -> 403
    fac_list_res = client.get("/api/reviews", headers=faculty_auth_headers)
    assert fac_list_res.status_code == 403

    # 3. Reviewer CAN list review cases -> 200
    rev_list_res = client.get("/api/reviews", headers=reviewer_auth_headers)
    assert rev_list_res.status_code == 200

    # 4. Other unassigned faculty cannot access discrepancy for this answer -> 403
    other_res = client.get(f"/api/answers/{answer_id}/discrepancy", headers=other_headers)
    assert other_res.status_code == 403

    # 5. Assigned faculty can access AFTER evaluation submission -> 200
    assigned_res = client.get(f"/api/answers/{answer_id}/discrepancy", headers=faculty_auth_headers)
    assert assigned_res.status_code == 200

    # 6. Anti-anchoring: If faculty has NOT submitted an evaluation yet, they CANNOT view discrepancy
    # Create an answer assigned to faculty but not evaluated yet
    exam = academic_setup["examination"]
    unev_student = Student(
        register_number="DB2026_UNEV",
        name="Unevaluated Student",
        division="A",
        email="unev@example.com",
    )
    db_session.add(unev_student)
    db_session.flush()

    faculty = academic_setup["faculty"]
    img_bytes = generate_png_bytes()
    upload_res = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": unev_student.id},
        files={"file": ("sheet.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )

    unevaluated_answer_id = upload_res.json()["answers"][0]["id"]
    assign_res = client.post(
        "/api/assignments/",
        json={
            "answer_id": unevaluated_answer_id,
            "faculty_id": faculty.id,
            "assignment_type": AssignmentType.PRIMARY.value,
        },
        headers=admin_auth_headers,
    )
    assert assign_res.status_code == 201

    # Faculty tries to inspect discrepancy before evaluating -> 403 Forbidden
    pre_eval_res = client.get(f"/api/answers/{unevaluated_answer_id}/discrepancy", headers=faculty_auth_headers)
    assert pre_eval_res.status_code == 403
    assert "until human faculty evaluation has been submitted" in pre_eval_res.json()["detail"].lower()
