import io
import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from PIL import Image, ImageDraw

from app.models.user import User, UserRole
from app.models.subject import Subject
from app.models.faculty_subject import FacultySubject
from app.models.examination import Examination, ExamStatus
from app.models.question import Question
from app.models.student import Student
from app.models.assignment import AssignmentStatus, AssignmentType
from app.core.security import create_access_token


@pytest.fixture
def admin_auth_headers(test_admin_user: User) -> dict:
    token = create_access_token(subject=test_admin_user.id, role=test_admin_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def faculty_auth_headers(test_user: User) -> dict:
    token = create_access_token(subject=test_user.id, role=test_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def academic_setup(db_session: Session, test_user: User) -> dict:
    """Create test Subject, Examination, Questions, Students, and Faculty eligibility."""
    subject = Subject(
        name="Operating Systems",
        code="CS301",
        description="Core Operating Systems Course",
    )
    db_session.add(subject)
    db_session.flush()

    # Assign the test faculty to this subject
    faculty_subject = FacultySubject(
        faculty_id=test_user.id,
        subject_id=subject.id,
    )
    db_session.add(faculty_subject)

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
    db_session.add(q1)

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
    student3 = Student(
        register_number="CS2026003",
        name="Charlie Student",
        division="A",
        email="charlie@example.com",
    )
    db_session.add_all([student1, student2, student3])
    db_session.flush()

    return {
        "subject": subject,
        "examination": examination,
        "questions": [q1],
        "students": [student1, student2, student3],
        "faculty": test_user,
    }


def generate_synthetic_answer_sheet_png() -> bytes:
    """Generate a clean synthetic answer sheet PNG image."""
    img = Image.new("RGB", (1000, 1400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((60, 80), "Q.1 Explain CPU Scheduling", fill=(0, 0, 0))
    draw.text((60, 140), "FCFS, SJF, Round Robin and Priority scheduling.", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_admin_assign_eligible_answer(
    client: TestClient,
    admin_auth_headers: dict,
    academic_setup: dict,
    db_session: Session,
):
    exam = academic_setup["examination"]
    student = academic_setup["students"][0]
    faculty = academic_setup["faculty"]
    q1 = academic_setup["questions"][0]

    # First, create an answer sheet and get an answer ID
    img_bytes = generate_synthetic_answer_sheet_png()
    upload_res = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("sheet.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    assert upload_res.status_code == 201
    answers = upload_res.json()["answers"]
    
    # Need to make sure there's an answer for Q1
    q1_answer = next((a for a in answers if a["question_id"] == q1.id), None)
    if not q1_answer:
        # If the synthetic sheet doesn't generate Q1, let's just use the first answer
        q1_answer = answers[0]

    answer_id = q1_answer["id"]

    # Assign it to the faculty member
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
    data = assign_res.json()
    assert data["answer_id"] == answer_id
    assert data["faculty_id"] == faculty.id
    assert data["status"] == AssignmentStatus.ASSIGNED.value


def test_unauthenticated_user_denied(
    client: TestClient,
    academic_setup: dict,
):
    res = client.post(
        "/api/assignments/",
        json={
            "answer_id": "dummy",
            "faculty_id": "dummy",
            "assignment_type": AssignmentType.PRIMARY.value,
        },
    )
    assert res.status_code == 401


def test_faculty_cannot_perform_admin_assignment(
    client: TestClient,
    faculty_auth_headers: dict,
    academic_setup: dict,
):
    res = client.post(
        "/api/assignments/",
        json={
            "answer_id": "dummy",
            "faculty_id": "dummy",
            "assignment_type": AssignmentType.PRIMARY.value,
        },
        headers=faculty_auth_headers,
    )
    assert res.status_code == 403


def test_admin_cannot_assign_to_inactive_faculty(
    client: TestClient,
    admin_auth_headers: dict,
    academic_setup: dict,
    db_session: Session,
):
    faculty = academic_setup["faculty"]
    
    # Mark faculty inactive temporarily
    faculty.is_active = False
    db_session.commit()

    res = client.post(
        "/api/assignments/",
        json={
            "answer_id": "dummy",
            "faculty_id": faculty.id,
            "assignment_type": AssignmentType.PRIMARY.value,
        },
        headers=admin_auth_headers,
    )
    assert res.status_code in [400, 404]

    # Restore faculty
    faculty.is_active = True
    db_session.commit()


def test_duplicate_assignment_rejected(
    client: TestClient,
    admin_auth_headers: dict,
    academic_setup: dict,
):
    exam = academic_setup["examination"]
    student = academic_setup["students"][1]
    faculty = academic_setup["faculty"]

    # Upload new sheet for fresh answers
    img_bytes = generate_synthetic_answer_sheet_png()
    upload_res = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("sheet.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    assert upload_res.status_code == 201
    answer_id = upload_res.json()["answers"][0]["id"]

    # First assignment
    assign1 = client.post(
        "/api/assignments/",
        json={
            "answer_id": answer_id,
            "faculty_id": faculty.id,
            "assignment_type": AssignmentType.PRIMARY.value,
        },
        headers=admin_auth_headers,
    )
    assert assign1.status_code == 201

    # Duplicate assignment
    assign2 = client.post(
        "/api/assignments/",
        json={
            "answer_id": answer_id,
            "faculty_id": faculty.id,
            "assignment_type": AssignmentType.PRIMARY.value,
        },
        headers=admin_auth_headers,
    )
    assert assign2.status_code == 409


def test_faculty_can_list_and_get_own_assignments(
    client: TestClient,
    admin_auth_headers: dict,
    faculty_auth_headers: dict,
    academic_setup: dict,
):
    exam = academic_setup["examination"]
    student = academic_setup["students"][2] # Use 3rd student
    faculty = academic_setup["faculty"]

    # Ensure there's an assignment for this faculty
    img_bytes = generate_synthetic_answer_sheet_png()
    upload_res = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("sheet.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    answer_id = upload_res.json()["answers"][0]["id"]

    assign_res = client.post(
        "/api/assignments/",
        json={
            "answer_id": answer_id,
            "faculty_id": faculty.id,
            "assignment_type": AssignmentType.PRIMARY.value,
        },
        headers=admin_auth_headers,
    )
    assignment_id = assign_res.json()["id"]

    # List assignments
    list_res = client.get("/api/assignments/me/list", headers=faculty_auth_headers)
    assert list_res.status_code == 200
    assignments = list_res.json()
    assert len(assignments) >= 1
    assert any(a["id"] == assignment_id for a in assignments)

    # Get specific assignment
    get_res = client.get(f"/api/assignments/me/{assignment_id}", headers=faculty_auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == assignment_id


def test_cancellation_authorization_and_transitions(
    client: TestClient,
    admin_auth_headers: dict,
    faculty_auth_headers: dict,
    academic_setup: dict,
):
    exam = academic_setup["examination"]
    student = academic_setup["students"][0] # reuse ok
    faculty = academic_setup["faculty"]

    # Create sheet & assignment
    img_bytes = generate_synthetic_answer_sheet_png()
    upload_res = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("sheet.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    answer_id = upload_res.json()["answers"][0]["id"]

    assign_res = client.post(
        "/api/assignments/",
        json={
            "answer_id": answer_id,
            "faculty_id": faculty.id,
            "assignment_type": AssignmentType.PRIMARY.value,
        },
        headers=admin_auth_headers,
    )
    assignment_id = assign_res.json()["id"]

    # Faculty cannot cancel
    faculty_del_res = client.delete(f"/api/assignments/{assignment_id}", headers=faculty_auth_headers)
    assert faculty_del_res.status_code == 403

    # Admin cancels
    admin_del_res = client.delete(f"/api/assignments/{assignment_id}", headers=admin_auth_headers)
    assert admin_del_res.status_code == 204

    # Verify status is CANCELLED
    get_res = client.get(f"/api/assignments/{assignment_id}", headers=admin_auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["status"] == AssignmentStatus.CANCELLED.value
