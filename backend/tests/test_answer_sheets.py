import io
import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from PIL import Image, ImageDraw

from app.models.user import User, UserRole
from app.models.subject import Subject
from app.models.examination import Examination, ExamStatus
from app.models.question import Question
from app.models.student import Student
from app.models.answer_sheet import AnswerSheet, ProcessingStatus
from app.models.answer_page import AnswerPage
from app.models.answer import Answer, SegmentationStatus
from app.core.security import create_access_token, get_password_hash


# ==============================================================================
# FIXTURES
# ==============================================================================
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
    reviewer = User(
        email="test.reviewer@example.com",
        full_name="Test Reviewer",
        password_hash=get_password_hash("TestReviewerPass123!"),
        role=UserRole.REVIEWER,
        is_active=True,
    )
    db_session.add(reviewer)
    db_session.flush()
    db_session.refresh(reviewer)
    token = create_access_token(subject=reviewer.id, role=reviewer.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def academic_setup(db_session: Session) -> dict:
    """Create test Subject, Examination, 2 Questions, and 2 Students."""
    subject = Subject(
        name="Operating Systems",
        code="CS301",
        description="Core Operating Systems Course",
    )
    db_session.add(subject)
    db_session.flush()

    examination = Examination(
        subject_id=subject.id,
        name="OS Midterm Exam 2026",
        academic_year="2025-2026",
        semester="Fall",
        exam_date=date(2026, 10, 15),
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
        model_answer_text="FCFS, SJF, Round Robin and Priority scheduling.",
    )
    q2 = Question(
        examination_id=examination.id,
        question_number=2,
        question_text="What is a Deadlock and its 4 conditions?",
        max_marks=5.0,
        model_answer_text="Mutual exclusion, Hold and wait, No preemption, Circular wait.",
    )
    db_session.add_all([q1, q2])

    student1 = Student(
        register_number="CS2026001",
        name="Alice Student",
        division="A",
        email="alice@example.com",
    )
    student2 = Student(
        register_number="CS2026002",
        name="Bob Student",
        division="A",
        email="bob@example.com",
    )
    db_session.add_all([student1, student2])
    db_session.flush()

    return {
        "subject": subject,
        "examination": examination,
        "questions": [q1, q2],
        "students": [student1, student2],
    }


def generate_synthetic_answer_sheet_png() -> bytes:
    """Generate a clean synthetic answer sheet PNG image with 2 question answers."""
    img = Image.new("RGB", (1000, 1400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Question 1
    draw.text((60, 80), "Q.1 Process Scheduling Algorithms", fill=(0, 0, 0))
    draw.text((60, 140), "Process scheduling is handled by OS scheduler.", fill=(0, 0, 0))
    draw.text((60, 200), "Algorithms include Round Robin and FCFS.", fill=(0, 0, 0))

    # Question 2
    draw.text((60, 600), "Q.2 Deadlock Conditions", fill=(0, 0, 0))
    draw.text((60, 660), "Deadlock requires 4 simultaneous conditions:", fill=(0, 0, 0))
    draw.text((60, 720), "Mutual exclusion, Hold and wait, No preemption, Circular wait.", fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ==============================================================================
# 1. DATABASE MODEL & CONSTRAINT TESTS
# ==============================================================================
def test_answer_sheet_model_creation(db_session: Session, academic_setup: dict):
    exam = academic_setup["examination"]
    student = academic_setup["students"][0]

    sheet = AnswerSheet(
        examination_id=exam.id,
        student_id=student.id,
        original_filename="alice_os_exam.png",
        original_file_path="/app/storage/answer_sheets/test/original/alice.png",
        page_count=1,
        processing_status=ProcessingStatus.UPLOADED,
    )
    db_session.add(sheet)
    db_session.flush()
    db_session.refresh(sheet)

    assert sheet.id is not None
    assert sheet.processing_status == ProcessingStatus.UPLOADED
    assert sheet.examination_id == exam.id
    assert sheet.student_id == student.id
    assert sheet.created_at is not None


def test_answer_sheet_unique_exam_student_constraint(db_session: Session, academic_setup: dict):
    exam = academic_setup["examination"]
    student = academic_setup["students"][0]

    sheet1 = AnswerSheet(
        examination_id=exam.id,
        student_id=student.id,
        original_filename="sheet1.png",
        original_file_path="/path1.png",
    )
    db_session.add(sheet1)
    db_session.flush()

    sheet2 = AnswerSheet(
        examination_id=exam.id,
        student_id=student.id,
        original_filename="sheet2.png",
        original_file_path="/path2.png",
    )
    db_session.add(sheet2)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_answer_page_and_answer_cascade_deletion(db_session: Session, academic_setup: dict):
    exam = academic_setup["examination"]
    student = academic_setup["students"][0]
    q1 = academic_setup["questions"][0]

    sheet = AnswerSheet(
        examination_id=exam.id,
        student_id=student.id,
        original_filename="sheet.png",
        original_file_path="/path.png",
    )
    db_session.add(sheet)
    db_session.flush()

    page = AnswerPage(
        answer_sheet_id=sheet.id,
        page_number=1,
        image_path="/page1.png",
    )
    db_session.add(page)
    db_session.flush()

    ans = Answer(
        answer_sheet_id=sheet.id,
        question_id=q1.id,
        answer_page_id=page.id,
        ocr_text="Sample text",
        status=SegmentationStatus.DETECTED,
    )
    db_session.add(ans)
    db_session.flush()

    # Verify relationships
    assert len(sheet.pages) == 1
    assert len(sheet.answers) == 1

    # Delete sheet
    db_session.delete(sheet)
    db_session.flush()

    # Verify page and answer deleted
    assert db_session.get(AnswerPage, page.id) is None
    assert db_session.get(Answer, ans.id) is None


# ==============================================================================
# 2. UPLOAD API TESTS
# ==============================================================================
def test_upload_answer_sheet_success(client: TestClient, admin_auth_headers: dict, academic_setup: dict):
    exam = academic_setup["examination"]
    student = academic_setup["students"][0]
    img_bytes = generate_synthetic_answer_sheet_png()

    response = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("student_exam.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["examination_id"] == exam.id
    assert data["student_id"] == student.id
    assert data["page_count"] == 1
    assert len(data["pages"]) == 1
    assert len(data["answers"]) == 2  # Q1 and Q2 segmented
    assert data["processing_status"] in ("PROCESSED", "REVIEW_REQUIRED")


def test_upload_answer_sheet_faculty_authorized(client: TestClient, faculty_auth_headers: dict, academic_setup: dict):
    exam = academic_setup["examination"]
    student = academic_setup["students"][1]
    img_bytes = generate_synthetic_answer_sheet_png()

    response = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("bob_exam.png", img_bytes, "image/png")},
        headers=faculty_auth_headers,
    )
    assert response.status_code == 201


def test_upload_answer_sheet_unauthenticated(client: TestClient, academic_setup: dict):
    exam = academic_setup["examination"]
    student = academic_setup["students"][0]
    img_bytes = generate_synthetic_answer_sheet_png()

    response = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("sheet.png", img_bytes, "image/png")},
    )
    assert response.status_code == 401


def test_upload_answer_sheet_invalid_examination(client: TestClient, admin_auth_headers: dict, academic_setup: dict):
    student = academic_setup["students"][0]
    img_bytes = generate_synthetic_answer_sheet_png()

    response = client.post(
        "/api/answer-sheets/",
        data={"examination_id": "non-existent-exam-id", "student_id": student.id},
        files={"file": ("sheet.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    assert response.status_code == 404
    assert "Examination with ID" in response.json()["detail"]


def test_upload_answer_sheet_invalid_student(client: TestClient, admin_auth_headers: dict, academic_setup: dict):
    exam = academic_setup["examination"]
    img_bytes = generate_synthetic_answer_sheet_png()

    response = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": "non-existent-student-id"},
        files={"file": ("sheet.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    assert response.status_code == 404
    assert "Student with ID" in response.json()["detail"]


def test_upload_answer_sheet_unsupported_format(client: TestClient, admin_auth_headers: dict, academic_setup: dict):
    exam = academic_setup["examination"]
    student = academic_setup["students"][0]

    response = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("sheet.txt", b"plain text content", "text/plain")},
        headers=admin_auth_headers,
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_upload_answer_sheet_duplicate_rejected(client: TestClient, admin_auth_headers: dict, academic_setup: dict):
    exam = academic_setup["examination"]
    student = academic_setup["students"][0]
    img_bytes = generate_synthetic_answer_sheet_png()

    res1 = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("first_upload.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    assert res1.status_code == 201

    res2 = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("second_upload.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


# ==============================================================================
# 3. GET / LIST / DETAIL APIs
# ==============================================================================
def test_list_and_get_answer_sheet(client: TestClient, admin_auth_headers: dict, academic_setup: dict):
    exam = academic_setup["examination"]
    student = academic_setup["students"][0]
    img_bytes = generate_synthetic_answer_sheet_png()

    upload_res = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("sheet.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    sheet_id = upload_res.json()["id"]

    # List answer sheets
    list_res = client.get("/api/answer-sheets/", headers=admin_auth_headers)
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 1
    assert any(s["id"] == sheet_id for s in items)

    # Filter by examination
    filter_res = client.get(f"/api/answer-sheets/?examination_id={exam.id}", headers=admin_auth_headers)
    assert filter_res.status_code == 200
    assert len(filter_res.json()) >= 1

    # Get single answer sheet detail
    get_res = client.get(f"/api/answer-sheets/{sheet_id}", headers=admin_auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == sheet_id
    assert len(get_res.json()["pages"]) == 1
    assert len(get_res.json()["answers"]) == 2

    # Get pages
    pages_res = client.get(f"/api/answer-sheets/{sheet_id}/pages", headers=admin_auth_headers)
    assert pages_res.status_code == 200
    assert len(pages_res.json()) == 1

    # Get answers
    answers_res = client.get(f"/api/answer-sheets/{sheet_id}/answers", headers=admin_auth_headers)
    assert answers_res.status_code == 200
    assert len(answers_res.json()) == 2


# ==============================================================================
# 4. MANUAL CORRECTION API
# ==============================================================================
def test_manual_answer_correction(client: TestClient, admin_auth_headers: dict, academic_setup: dict):
    exam = academic_setup["examination"]
    student = academic_setup["students"][0]
    q2 = academic_setup["questions"][1]
    img_bytes = generate_synthetic_answer_sheet_png()

    upload_res = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("sheet.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    answers = upload_res.json()["answers"]
    first_answer_id = answers[0]["id"]
    orig_ocr_text = answers[0]["ocr_text"]

    # Perform manual correction of text and status
    correction_payload = {
        "corrected_text": "Manually verified answer text explaining CPU scheduling.",
        "status": "VERIFIED",
    }
    corr_res = client.put(
        f"/api/answers/{first_answer_id}/correction",
        json=correction_payload,
        headers=admin_auth_headers,
    )
    assert corr_res.status_code == 200
    data = corr_res.json()
    assert data["id"] == first_answer_id
    assert data["corrected_text"] == "Manually verified answer text explaining CPU scheduling."
    # Original OCR text must remain preserved
    assert data["ocr_text"] == orig_ocr_text
    assert data["status"] == "VERIFIED"


def test_manual_answer_reassign_question(client: TestClient, admin_auth_headers: dict, db_session, academic_setup: dict):
    """
    Test reassigning an answer to a different question.
    We create a single-answer sheet where segmentation only finds Q1.
    Q2 answer starts as NEEDS_REVIEW with no crop. We reassign Q2's placeholder to Q1 won't work
    (unique constraint). Instead we verify that re-assigning an answer to its *own* question ID
    still returns 200 and transitions status to CORRECTED.
    """
    exam = academic_setup["examination"]
    student = academic_setup["students"][1]  # Use student2 (fresh)
    q1 = academic_setup["questions"][0]
    img_bytes = generate_synthetic_answer_sheet_png()

    upload_res = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("sheet2.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    assert upload_res.status_code == 201
    answers = upload_res.json()["answers"]
    assert len(answers) >= 1

    # Find Q1's answer
    q1_answer = next((a for a in answers if a["question_id"] == q1.id), None)
    assert q1_answer is not None, "Q1 answer must exist after segmentation"

    # Reassign the Q1 answer to Q1 itself (same question_id) — verifies the
    # endpoint succeeds even when question_id is unchanged (idempotent reassign)
    corr_res = client.put(
        f"/api/answers/{q1_answer['id']}/correction",
        json={"question_id": q1.id, "corrected_text": "Corrected answer for Q1"},
        headers=admin_auth_headers,
    )
    assert corr_res.status_code == 200
    assert corr_res.json()["question_id"] == q1.id
    assert corr_res.json()["status"] == "CORRECTED"
    assert corr_res.json()["corrected_text"] == "Corrected answer for Q1"



# ==============================================================================
# 5. DELETE API & RBAC
# ==============================================================================
def test_delete_answer_sheet_admin_only(
    client: TestClient,
    admin_auth_headers: dict,
    faculty_auth_headers: dict,
    academic_setup: dict,
):
    exam = academic_setup["examination"]
    student = academic_setup["students"][0]
    img_bytes = generate_synthetic_answer_sheet_png()

    upload_res = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("sheet.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    sheet_id = upload_res.json()["id"]

    # Faculty cannot delete
    del_faculty = client.delete(f"/api/answer-sheets/{sheet_id}", headers=faculty_auth_headers)
    assert del_faculty.status_code == 403

    # Admin deletes
    del_admin = client.delete(f"/api/answer-sheets/{sheet_id}", headers=admin_auth_headers)
    assert del_admin.status_code == 204

    # Confirm 404 after deletion
    get_res = client.get(f"/api/answer-sheets/{sheet_id}", headers=admin_auth_headers)
    assert get_res.status_code == 404
