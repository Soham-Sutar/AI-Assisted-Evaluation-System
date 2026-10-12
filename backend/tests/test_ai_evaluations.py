import io
import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from PIL import Image, ImageDraw

from app.core.config import settings
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
from app.services.ai_evaluator import evaluate_student_answer, strip_marker_prefix
from app.ai.scorer import evaluate_answer


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
        email="test.reviewer@example.com",
        full_name="Test Reviewer",
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
        email="other.faculty@example.com",
        full_name="Other Faculty",
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
    draw.text((50, 50), "Q.1 Process scheduling algorithms include FCFS and Round Robin.", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def academic_setup(db_session: Session, test_user: User) -> dict:
    subject = Subject(name="Distributed Systems", code="CS401", description="Core DS Course")
    db_session.add(subject)
    db_session.flush()

    db_session.add(FacultySubject(faculty_id=test_user.id, subject_id=subject.id))

    examination = Examination(
        subject_id=subject.id,
        name="DS Midterm Exam 2026",
        academic_year="2025-2026",
        semester="Fall",
        exam_date=date(2026, 10, 20),
        total_marks=10.0,
        status=ExamStatus.READY,
    )
    db_session.add(examination)
    db_session.flush()

    q1 = Question(
        examination_id=examination.id,
        question_number=1,
        question_text="Explain Process Scheduling algorithms.",
        max_marks=5.0,
        model_answer_text="Process scheduling handles execution queues using FCFS, SJF, and Round Robin algorithms.",
        rubric_json={
            "points": [
                {"description": "Defines process scheduling and queues", "marks": 2.0},
                {"description": "Explains FCFS and Round Robin algorithms", "marks": 3.0},
            ]
        },
    )
    db_session.add(q1)

    student1 = Student(register_number="DS2026001", name="Bob Student", division="A", email="bob@example.com")
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
def prepared_answer(client: TestClient, admin_auth_headers: dict, academic_setup: dict, db_session: Session) -> dict:
    exam = academic_setup["examination"]
    student = academic_setup["student"]
    faculty = academic_setup["faculty"]

    # Upload answer sheet
    img_bytes = generate_png_bytes()
    upload_res = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("sheet.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    assert upload_res.status_code == 201
    sheet_data = upload_res.json()
    answer_id = sheet_data["answers"][0]["id"]

    # Populate answer OCR text so evaluation has valid text
    ans = db_session.get(Answer, answer_id)
    ans.ocr_text = "Process scheduling algorithms include FCFS, SJF, and Round Robin scheduling to manage process queues."
    ans.ocr_confidence = 88.0
    ans.status = SegmentationStatus.VERIFIED
    db_session.commit()

    # Assign to faculty
    assign_res = client.post(
        "/api/assignments/",
        json={
            "answer_id": answer_id,
            "faculty_id": faculty.id,
            "assignment_type": AssignmentType.PRIMARY.value,
        },
        headers=admin_auth_headers,
    )
    assert assign_res.status_code == 201
    assignment_data = assign_res.json()

    return {
        "answer_id": answer_id,
        "assignment_id": assignment_data["id"],
        "faculty_id": faculty.id,
    }


# 1. Eligible AI evaluation succeeds and is persisted
def test_eligible_ai_evaluation_succeeds_and_persists(
    client: TestClient,
    admin_auth_headers: dict,
    prepared_answer: dict,
    db_session: Session,
):
    answer_id = prepared_answer["answer_id"]
    res = client.post(
        f"/api/answers/{answer_id}/ai-evaluate",
        headers=admin_auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["answer_id"] == answer_id
    assert data["status"] == "COMPLETED"
    assert data["ai_marks"] is not None
    assert 0.0 <= data["ai_marks"] <= 5.0
    assert data["max_marks"] == 5.0
    assert data["final_ai_score"] is not None
    assert data["confidence_score"] is not None
    assert data["semantic_similarity"] is not None
    assert data["keypoint_score"] is not None
    assert data["explanation_json"] is not None
    assert data["model_name"] != ""

    # Verify directly in DB
    db_ai = db_session.query(AIEvaluation).filter(AIEvaluation.answer_id == answer_id).first()
    assert db_ai is not None
    assert db_ai.status == AIEvaluationStatus.COMPLETED
    assert db_ai.ai_marks == data["ai_marks"]


# 2. Score is strictly within valid bounds [0, max_marks]
def test_ai_score_within_valid_bounds(
    client: TestClient,
    reviewer_auth_headers: dict,
    prepared_answer: dict,
):
    answer_id = prepared_answer["answer_id"]
    res = client.post(
        f"/api/answers/{answer_id}/ai-evaluate",
        headers=reviewer_auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert 0.0 <= data["ai_marks"] <= data["max_marks"]
    assert 0.0 <= data["final_ai_score"] <= 1.0


# 3. Model/version metadata is stored
def test_model_metadata_stored(
    client: TestClient,
    admin_auth_headers: dict,
    prepared_answer: dict,
):
    answer_id = prepared_answer["answer_id"]
    res = client.post(
        f"/api/answers/{answer_id}/ai-evaluate",
        headers=admin_auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "model_name" in data
    assert len(data["model_name"]) > 0
    assert "explanation_json" in data
    assert "method" in data["explanation_json"]


# 4. Faculty marks are not inputs to AI scoring function
def test_faculty_marks_not_inputs_to_ai_scoring():
    import inspect
    sig = inspect.signature(evaluate_answer)
    param_names = list(sig.parameters.keys())
    assert "faculty_marks" not in param_names
    assert "faculty_score" not in param_names
    assert "human_marks" not in param_names

    # Direct function evaluation gives identical result regardless of human context
    res1 = evaluate_answer("Process scheduling includes FCFS and SJF.", "FCFS and SJF scheduling.", 5.0)
    res2 = evaluate_answer("Process scheduling includes FCFS and SJF.", "FCFS and SJF scheduling.", 5.0)
    assert res1.ai_marks == res2.ai_marks


# 5. Faculty evaluation remains completely unchanged after AI evaluation
def test_faculty_evaluation_remains_unchanged(
    client: TestClient,
    faculty_auth_headers: dict,
    admin_auth_headers: dict,
    prepared_answer: dict,
    db_session: Session,
):
    answer_id = prepared_answer["answer_id"]
    assignment_id = prepared_answer["assignment_id"]

    # 1. Faculty evaluates first
    eval_res = client.post(
        "/api/evaluations/",
        json={"assignment_id": assignment_id, "marks_awarded": 3.5, "comments": "Decent effort"},
        headers=faculty_auth_headers,
    )
    assert eval_res.status_code == 201

    # 2. Trigger independent AI evaluation
    ai_res = client.post(
        f"/api/answers/{answer_id}/ai-evaluate",
        headers=admin_auth_headers,
    )
    assert ai_res.status_code == 200

    # 3. Verify faculty evaluation in DB is totally unmodified
    human_eval = db_session.query(Evaluation).filter(Evaluation.answer_id == answer_id).first()
    assert human_eval is not None
    assert human_eval.marks_awarded == 3.5
    assert human_eval.comments == "Decent effort"


# 6. Unauthorized triggering and anti-anchoring retrieval rejected
def test_unauthorized_triggering_and_retrieval(
    client: TestClient,
    faculty_auth_headers: dict,
    admin_auth_headers: dict,
    other_faculty_auth_headers: tuple[dict, User],
    prepared_answer: dict,
):
    answer_id = prepared_answer["answer_id"]
    assignment_id = prepared_answer["assignment_id"]
    other_headers, _ = other_faculty_auth_headers

    # Unauthenticated trigger rejected
    res_unauth = client.post(f"/api/answers/{answer_id}/ai-evaluate")
    assert res_unauth.status_code == 401

    # Faculty cannot trigger AI evaluation (restricted to ADMIN / REVIEWER)
    res_faculty_trigger = client.post(
        f"/api/answers/{answer_id}/ai-evaluate",
        headers=faculty_auth_headers,
    )
    assert res_faculty_trigger.status_code == 403

    # Admin triggers evaluation
    admin_res = client.post(f"/api/answers/{answer_id}/ai-evaluate", headers=admin_auth_headers)
    assert admin_res.status_code == 200

    # Assigned faculty tries to view AI evaluation BEFORE submitting their own marks -> 403 Forbidden (Anti-anchoring)
    res_anchoring = client.get(
        f"/api/answers/{answer_id}/ai-evaluation",
        headers=faculty_auth_headers,
    )
    assert res_anchoring.status_code == 403
    assert "hidden" in res_anchoring.json()["detail"].lower()

    # Unassigned faculty tries to view -> 403 Forbidden (IDOR prevention)
    res_idor = client.get(
        f"/api/answers/{answer_id}/ai-evaluation",
        headers=other_headers,
    )
    assert res_idor.status_code == 403

    # Faculty submits human marks
    client.post(
        "/api/evaluations/",
        json={"assignment_id": assignment_id, "marks_awarded": 4.0},
        headers=faculty_auth_headers,
    )

    # Now faculty CAN view AI evaluation
    res_revealed = client.get(
        f"/api/answers/{answer_id}/ai-evaluation",
        headers=faculty_auth_headers,
    )
    assert res_revealed.status_code == 200
    assert res_revealed.json()["answer_id"] == answer_id


# 7. Missing answer, model answer, or rubric handled correctly
def test_missing_entities_handled_gracefully(
    client: TestClient,
    admin_auth_headers: dict,
    academic_setup: dict,
    db_session: Session,
):
    # Non-existent answer -> 404
    res_404 = client.post(
        "/api/answers/non-existent-uuid/ai-evaluate",
        headers=admin_auth_headers,
    )
    assert res_404.status_code == 404

    # Create question with no model answer and no rubric
    exam = academic_setup["examination"]
    q_empty = Question(
        examination_id=exam.id,
        question_number=99,
        question_text="Explain Quantum Computing.",
        max_marks=10.0,
        model_answer_text=None,
        rubric_json=None,
    )
    db_session.add(q_empty)
    db_session.flush()

    # Create answer for this question
    student = academic_setup["student"]
    img_bytes = generate_png_bytes()
    upload_res = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("sheet2.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    sheet_data = upload_res.json()
    empty_ans = next(a for a in sheet_data["answers"] if a["question_id"] == q_empty.id)
    ans_id = empty_ans["id"]
    ans = db_session.get(Answer, ans_id)
    ans.ocr_text = "Some answer text explaining quantum computing principles."
    db_session.commit()

    # Trigger AI evaluation on question with no reference answer -> status FAILED, doesn't crash
    res_fail = client.post(f"/api/answers/{ans_id}/ai-evaluate", headers=admin_auth_headers)
    assert res_fail.status_code == 200
    data = res_fail.json()
    assert data["status"] == "FAILED"
    assert "error_message" in data
    assert data["ai_marks"] is None


# 8. Model failure does not corrupt human evaluation
def test_model_failure_does_not_corrupt_human_eval(
    client: TestClient,
    admin_auth_headers: dict,
    faculty_auth_headers: dict,
    prepared_answer: dict,
    db_session: Session,
    monkeypatch,
):
    answer_id = prepared_answer["answer_id"]
    assignment_id = prepared_answer["assignment_id"]

    # Faculty evaluates
    client.post(
        "/api/evaluations/",
        json={"assignment_id": assignment_id, "marks_awarded": 4.5},
        headers=faculty_auth_headers,
    )

    # Monkeypatch scorer to simulate an unexpected model inference crash
    import app.services.ai_evaluator as service
    def mock_evaluate_answer(*args, **kwargs):
        raise RuntimeError("GPU out of memory or inference server unavailable")
    monkeypatch.setattr(service, "evaluate_answer", mock_evaluate_answer)

    # Trigger AI evaluation
    res = client.post(f"/api/answers/{answer_id}/ai-evaluate", json={"force_reevaluate": True}, headers=admin_auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "FAILED"
    assert "RuntimeError" in data["error_message"]

    # Verify human evaluation is still 100% intact
    human_eval = db_session.query(Evaluation).filter(Evaluation.answer_id == answer_id).first()
    assert human_eval is not None
    assert human_eval.marks_awarded == 4.5


# 9. Idempotency policy: repeated requests return same evaluation unless force_reevaluate is True
def test_idempotency_and_reevaluation_policy(
    client: TestClient,
    admin_auth_headers: dict,
    prepared_answer: dict,
):
    answer_id = prepared_answer["answer_id"]

    # First evaluation
    res1 = client.post(f"/api/answers/{answer_id}/ai-evaluate", headers=admin_auth_headers)
    assert res1.status_code == 200
    data1 = res1.json()

    # Second evaluation without force -> returns same record
    res2 = client.post(f"/api/answers/{answer_id}/ai-evaluate", json={"force_reevaluate": False}, headers=admin_auth_headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data1["id"] == data2["id"]
    assert data1["created_at"] == data2["created_at"]

    # Third evaluation with force -> creates new evaluation
    res3 = client.post(f"/api/answers/{answer_id}/ai-evaluate", json={"force_reevaluate": True}, headers=admin_auth_headers)
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["id"] != data1["id"]


# 10. Helper function strip_marker_prefix test
def test_strip_marker_prefix():
    assert strip_marker_prefix("Q1. Hello world") == "Hello world"
    assert strip_marker_prefix("Question 2: Process scheduling") == "Process scheduling"
    assert strip_marker_prefix("1. Round robin algorithm") == "Round robin algorithm"
    assert strip_marker_prefix("Pure text without marker") == "Pure text without marker"
    assert strip_marker_prefix("") == ""
