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
def another_faculty_auth_headers(db_session: Session) -> tuple[dict, User]:
    user = User(
        email="another_faculty@example.com",
        full_name="Another Faculty",
        password_hash="fakehash",
        role=UserRole.FACULTY,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}, user


@pytest.fixture
def academic_setup(db_session: Session, test_user: User) -> dict:
    subject = Subject(name="Operating Systems", code="CS301", description="Core OS Course")
    db_session.add(subject)
    db_session.flush()

    db_session.add(FacultySubject(faculty_id=test_user.id, subject_id=subject.id))

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

    student1 = Student(register_number="CS2026001", name="Alice Student", division="A", email="alice@example.com")
    db_session.add(student1)
    db_session.flush()

    return {
        "subject": subject,
        "examination": examination,
        "questions": [q1],
        "students": [student1],
        "faculty": test_user,
    }


def generate_synthetic_answer_sheet_png() -> bytes:
    img = Image.new("RGB", (1000, 1400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((60, 80), "Q.1 Explain CPU Scheduling", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def assigned_answer(client: TestClient, admin_auth_headers: dict, academic_setup: dict) -> dict:
    exam = academic_setup["examination"]
    student = academic_setup["students"][0]
    faculty = academic_setup["faculty"]
    
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
    return assign_res.json()


def test_faculty_can_evaluate_own_assignment(client: TestClient, faculty_auth_headers: dict, assigned_answer: dict):
    res = client.post(
        "/api/evaluations/",
        json={
            "assignment_id": assigned_answer["id"],
            "marks_awarded": 4.5,
            "comments": "Good answer.",
        },
        headers=faculty_auth_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["marks_awarded"] == 4.5
    assert data["comments"] == "Good answer."
    assert data["assignment_id"] == assigned_answer["id"]
    
    # Check that assignment is completed
    get_res = client.get("/api/evaluations/me/list", headers=faculty_auth_headers)
    assert len(get_res.json()) >= 1


def test_unauthenticated_evaluation_denied(client: TestClient, assigned_answer: dict):
    res = client.post(
        "/api/evaluations/",
        json={
            "assignment_id": assigned_answer["id"],
            "marks_awarded": 4.5,
            "comments": "Good answer.",
        },
    )
    assert res.status_code == 401


def test_faculty_cannot_evaluate_another_faculty_assignment(
    client: TestClient, 
    another_faculty_auth_headers: tuple[dict, User], 
    assigned_answer: dict
):
    headers, _ = another_faculty_auth_headers
    res = client.post(
        "/api/evaluations/",
        json={
            "assignment_id": assigned_answer["id"],
            "marks_awarded": 4.5,
            "comments": "Good answer.",
        },
        headers=headers,
    )
    assert res.status_code == 403


def test_invalid_marks_rejected(client: TestClient, faculty_auth_headers: dict, assigned_answer: dict):
    # Negative marks
    res1 = client.post(
        "/api/evaluations/",
        json={
            "assignment_id": assigned_answer["id"],
            "marks_awarded": -1.0,
        },
        headers=faculty_auth_headers,
    )
    assert res1.status_code in [400, 422]

    # Exceeding max marks (which is 5.0 in the fixture)
    res2 = client.post(
        "/api/evaluations/",
        json={
            "assignment_id": assigned_answer["id"],
            "marks_awarded": 6.0,
        },
        headers=faculty_auth_headers,
    )
    assert res2.status_code in [400, 422]


def test_duplicate_submission_rejected(client: TestClient, faculty_auth_headers: dict, assigned_answer: dict):
    # First submission
    res1 = client.post(
        "/api/evaluations/",
        json={
            "assignment_id": assigned_answer["id"],
            "marks_awarded": 4.0,
        },
        headers=faculty_auth_headers,
    )
    assert res1.status_code == 201

    # Second submission
    res2 = client.post(
        "/api/evaluations/",
        json={
            "assignment_id": assigned_answer["id"],
            "marks_awarded": 4.0,
        },
        headers=faculty_auth_headers,
    )
    assert res2.status_code == 400
