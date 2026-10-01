import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.subject import Subject
from app.models.examination import Examination, ExamStatus
from app.models.question import Question
from app.models.student import Student
from app.core.security import create_access_token


@pytest.fixture
def admin_auth_headers(test_admin_user: User) -> dict:
    token = create_access_token(subject=test_admin_user.id, role=test_admin_user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def faculty_auth_headers(test_user: User) -> dict:
    token = create_access_token(subject=test_user.id, role=test_user.role.value)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. SUBJECT APIs
# ==============================================================================

def test_subject_admin_create(client: TestClient, admin_auth_headers: dict):
    response = client.post(
        "/api/subjects/",
        json={"name": "Database Management Systems", "code": "CS204", "description": "Relational databases"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["code"] == "CS204"
    assert data["name"] == "Database Management Systems"
    assert "id" in data


def test_subject_faculty_cannot_create(client: TestClient, faculty_auth_headers: dict):
    response = client.post(
        "/api/subjects/",
        json={"name": "Compiler Design", "code": "CS502"},
        headers=faculty_auth_headers,
    )
    assert response.status_code == 403


def test_subject_unauthenticated_denied(client: TestClient):
    response = client.get("/api/subjects/")
    assert response.status_code == 401


def test_subject_duplicate_code_rejected(client: TestClient, admin_auth_headers: dict):
    client.post(
        "/api/subjects/",
        json={"name": "Computer Networks", "code": "CS402"},
        headers=admin_auth_headers,
    )
    dup_res = client.post(
        "/api/subjects/",
        json={"name": "Advanced Networks", "code": "CS402"},
        headers=admin_auth_headers,
    )
    assert dup_res.status_code == 409
    assert "already exists" in dup_res.json()["detail"]


def test_subject_list_and_get(client: TestClient, admin_auth_headers: dict, faculty_auth_headers: dict):
    create_res = client.post(
        "/api/subjects/",
        json={"name": "Distributed Systems", "code": "CS604"},
        headers=admin_auth_headers,
    )
    subject_id = create_res.json()["id"]

    # Faculty can list
    list_res = client.get("/api/subjects/", headers=faculty_auth_headers)
    assert list_res.status_code == 200
    assert any(s["id"] == subject_id for s in list_res.json())

    # Faculty can get by ID
    get_res = client.get(f"/api/subjects/{subject_id}", headers=faculty_auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["code"] == "CS604"


def test_subject_update_and_delete(client: TestClient, admin_auth_headers: dict):
    create_res = client.post(
        "/api/subjects/",
        json={"name": "Temporary Subject", "code": "TMP101"},
        headers=admin_auth_headers,
    )
    subject_id = create_res.json()["id"]

    # Update
    update_res = client.put(
        f"/api/subjects/{subject_id}",
        json={"name": "Updated Subject", "code": "TMP102"},
        headers=admin_auth_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["code"] == "TMP102"

    # Delete
    del_res = client.delete(f"/api/subjects/{subject_id}", headers=admin_auth_headers)
    assert del_res.status_code == 204

    # Verify 404 after deletion
    get_res = client.get(f"/api/subjects/{subject_id}", headers=admin_auth_headers)
    assert get_res.status_code == 404


# ==============================================================================
# 2. FACULTY-SUBJECT ELIGIBILITY APIs
# ==============================================================================

def test_faculty_subject_admin_assignment(
    client: TestClient,
    admin_auth_headers: dict,
    test_user: User,
):
    # Create subject
    subj_res = client.post(
        "/api/subjects/",
        json={"name": "Cloud Computing", "code": "CS701"},
        headers=admin_auth_headers,
    )
    subject_id = subj_res.json()["id"]

    # Assign faculty to subject
    assign_res = client.post(
        "/api/faculty-subjects/",
        json={"faculty_id": test_user.id, "subject_id": subject_id},
        headers=admin_auth_headers,
    )
    assert assign_res.status_code == 201
    assignment = assign_res.json()
    assert assignment["faculty_id"] == test_user.id
    assert assignment["subject_id"] == subject_id
    assert assignment["subject_code"] == "CS701"


def test_faculty_subject_cannot_assign_non_faculty(
    client: TestClient,
    admin_auth_headers: dict,
    test_admin_user: User,
):
    subj_res = client.post(
        "/api/subjects/",
        json={"name": "Cybersecurity", "code": "CS801"},
        headers=admin_auth_headers,
    )
    subject_id = subj_res.json()["id"]

    # Attempt to assign an ADMIN user as faculty
    res = client.post(
        "/api/faculty-subjects/",
        json={"faculty_id": test_admin_user.id, "subject_id": subject_id},
        headers=admin_auth_headers,
    )
    assert res.status_code == 400
    assert "does not have the FACULTY role" in res.json()["detail"]


def test_faculty_subject_duplicate_rejected(
    client: TestClient,
    admin_auth_headers: dict,
    test_user: User,
):
    subj_res = client.post(
        "/api/subjects/",
        json={"name": "Machine Learning", "code": "CS901"},
        headers=admin_auth_headers,
    )
    subject_id = subj_res.json()["id"]

    client.post(
        "/api/faculty-subjects/",
        json={"faculty_id": test_user.id, "subject_id": subject_id},
        headers=admin_auth_headers,
    )
    dup_res = client.post(
        "/api/faculty-subjects/",
        json={"faculty_id": test_user.id, "subject_id": subject_id},
        headers=admin_auth_headers,
    )
    assert dup_res.status_code == 409


def test_faculty_subject_scoped_listing(
    client: TestClient,
    admin_auth_headers: dict,
    faculty_auth_headers: dict,
    test_user: User,
):
    subj_res = client.post(
        "/api/subjects/",
        json={"name": "Big Data Analytics", "code": "CS902"},
        headers=admin_auth_headers,
    )
    subject_id = subj_res.json()["id"]

    assign_res = client.post(
        "/api/faculty-subjects/",
        json={"faculty_id": test_user.id, "subject_id": subject_id},
        headers=admin_auth_headers,
    )
    assignment_id = assign_res.json()["id"]

    # Faculty listing returns their assigned subjects
    fac_list = client.get("/api/faculty-subjects/", headers=faculty_auth_headers)
    assert fac_list.status_code == 200
    assert any(a["id"] == assignment_id for a in fac_list.json())

    # Admin deletion
    del_res = client.delete(f"/api/faculty-subjects/{assignment_id}", headers=admin_auth_headers)
    assert del_res.status_code == 204


# ==============================================================================
# 3. EXAMINATION APIs
# ==============================================================================

def test_examination_admin_create_and_validation(client: TestClient, admin_auth_headers: dict):
    subj_res = client.post(
        "/api/subjects/",
        json={"name": "Microprocessors", "code": "EC301"},
        headers=admin_auth_headers,
    )
    subject_id = subj_res.json()["id"]

    # Invalid subject
    bad_res = client.post(
        "/api/examinations/",
        json={
            "subject_id": "nonexistent-id",
            "name": "Mid-Term",
            "academic_year": "2025-2026",
            "semester": "Semester 3",
        },
        headers=admin_auth_headers,
    )
    assert bad_res.status_code == 404

    # Valid create
    exam_res = client.post(
        "/api/examinations/",
        json={
            "subject_id": subject_id,
            "name": "Mid-Term Examination 2026",
            "academic_year": "2025-2026",
            "semester": "Semester 3",
            "exam_date": "2026-04-10",
            "total_marks": 50.0,
            "status": "DRAFT",
        },
        headers=admin_auth_headers,
    )
    assert exam_res.status_code == 201
    data = exam_res.json()
    assert data["name"] == "Mid-Term Examination 2026"
    assert data["subject_code"] == "EC301"
    assert data["status"] == "DRAFT"


def test_examination_faculty_cannot_create_or_delete(
    client: TestClient,
    admin_auth_headers: dict,
    faculty_auth_headers: dict,
):
    subj_res = client.post(
        "/api/subjects/",
        json={"name": "VLSI Design", "code": "EC401"},
        headers=admin_auth_headers,
    )
    subject_id = subj_res.json()["id"]

    # Faculty create attempt
    create_attempt = client.post(
        "/api/examinations/",
        json={
            "subject_id": subject_id,
            "name": "Faculty Exam Attempt",
            "academic_year": "2025-2026",
            "semester": "Semester 4",
        },
        headers=faculty_auth_headers,
    )
    assert create_attempt.status_code == 403

    # Create as admin
    admin_create = client.post(
        "/api/examinations/",
        json={
            "subject_id": subject_id,
            "name": "Admin Exam",
            "academic_year": "2025-2026",
            "semester": "Semester 4",
        },
        headers=admin_auth_headers,
    )
    exam_id = admin_create.json()["id"]

    # Faculty delete attempt
    del_attempt = client.delete(f"/api/examinations/{exam_id}", headers=faculty_auth_headers)
    assert del_attempt.status_code == 403

    # Faculty can view
    get_res = client.get(f"/api/examinations/{exam_id}", headers=faculty_auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Admin Exam"


# ==============================================================================
# 4. QUESTION APIs
# ==============================================================================

def test_question_crud_and_rubric_json(
    client: TestClient,
    admin_auth_headers: dict,
    faculty_auth_headers: dict,
):
    # Setup Subject & Exam
    subj_res = client.post(
        "/api/subjects/",
        json={"name": "Computer Architecture", "code": "CS305"},
        headers=admin_auth_headers,
    )
    exam_res = client.post(
        "/api/examinations/",
        json={
            "subject_id": subj_res.json()["id"],
            "name": "Arch Exam",
            "academic_year": "2025-2026",
            "semester": "Semester 3",
        },
        headers=admin_auth_headers,
    )
    examination_id = exam_res.json()["id"]

    rubric = {
        "points": [
            {"description": "Pipelining hazards explanation", "marks": 2.5},
            {"description": "Forwarding technique diagram", "marks": 2.5},
        ]
    }

    # Create Question
    q_create = client.post(
        f"/api/examinations/{examination_id}/questions/",
        json={
            "question_number": 1,
            "question_text": "Explain data hazards and operand forwarding in pipelining.",
            "max_marks": 5.0,
            "model_answer_text": "Data hazards occur when instructions depend on previous results...",
            "rubric_json": rubric,
        },
        headers=admin_auth_headers,
    )
    assert q_create.status_code == 201
    q_data = q_create.json()
    assert q_data["question_number"] == 1
    assert q_data["rubric_json"]["points"][0]["marks"] == 2.5
    question_id = q_data["id"]

    # Faculty cannot create question
    fac_create = client.post(
        f"/api/examinations/{examination_id}/questions/",
        json={"question_number": 2, "question_text": "Illegal Question", "max_marks": 5.0},
        headers=faculty_auth_headers,
    )
    assert fac_create.status_code == 403

    # Duplicate question number rejected
    dup_res = client.post(
        f"/api/examinations/{examination_id}/questions/",
        json={"question_number": 1, "question_text": "Duplicate Q1", "max_marks": 5.0},
        headers=admin_auth_headers,
    )
    assert dup_res.status_code == 409

    # Faculty can view questions
    list_res = client.get(
        f"/api/examinations/{examination_id}/questions/",
        headers=faculty_auth_headers,
    )
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # Update Question
    update_res = client.put(
        f"/api/examinations/{examination_id}/questions/{question_id}",
        json={"max_marks": 10.0},
        headers=admin_auth_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["max_marks"] == 10.0

    # Delete Question
    del_res = client.delete(
        f"/api/examinations/{examination_id}/questions/{question_id}",
        headers=admin_auth_headers,
    )
    assert del_res.status_code == 204


def test_question_validation_errors(client: TestClient, admin_auth_headers: dict):
    subj_res = client.post(
        "/api/subjects/",
        json={"name": "Discrete Mathematics", "code": "MATH201"},
        headers=admin_auth_headers,
    )
    exam_res = client.post(
        "/api/examinations/",
        json={
            "subject_id": subj_res.json()["id"],
            "name": "Math Quiz",
            "academic_year": "2025-2026",
            "semester": "Semester 2",
        },
        headers=admin_auth_headers,
    )
    examination_id = exam_res.json()["id"]

    # Invalid question_number (must be > 0)
    bad_num = client.post(
        f"/api/examinations/{examination_id}/questions/",
        json={"question_number": 0, "question_text": "Bad Question", "max_marks": 5.0},
        headers=admin_auth_headers,
    )
    assert bad_num.status_code == 422

    # Invalid max_marks (must be > 0)
    bad_marks = client.post(
        f"/api/examinations/{examination_id}/questions/",
        json={"question_number": 1, "question_text": "Bad Marks", "max_marks": -5.0},
        headers=admin_auth_headers,
    )
    assert bad_marks.status_code == 422


# ==============================================================================
# 5. STUDENT APIs
# ==============================================================================

def test_student_crud_and_uniqueness(
    client: TestClient,
    admin_auth_headers: dict,
    faculty_auth_headers: dict,
):
    # Admin Create Student
    create_res = client.post(
        "/api/students/",
        json={
            "register_number": "STU2026CS001",
            "name": "Grace Hopper",
            "division": "CS-A",
            "email": "grace.hopper@student.edu",
        },
        headers=admin_auth_headers,
    )
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["register_number"] == "STU2026CS001"
    student_id = data["id"]

    # Duplicate register number rejected
    dup_res = client.post(
        "/api/students/",
        json={"register_number": "STU2026CS001", "name": "Duplicate Grace"},
        headers=admin_auth_headers,
    )
    assert dup_res.status_code == 409

    # Faculty can list & view students
    list_res = client.get("/api/students/", headers=faculty_auth_headers)
    assert list_res.status_code == 200
    assert any(s["id"] == student_id for s in list_res.json())

    # Faculty cannot update/delete students
    fac_update = client.put(
        f"/api/students/{student_id}",
        json={"name": "Hacked Grace"},
        headers=faculty_auth_headers,
    )
    assert fac_update.status_code == 403

    fac_del = client.delete(f"/api/students/{student_id}", headers=faculty_auth_headers)
    assert fac_del.status_code == 403

    # Admin update & delete
    update_res = client.put(
        f"/api/students/{student_id}",
        json={"division": "CS-B"},
        headers=admin_auth_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["division"] == "CS-B"

    del_res = client.delete(f"/api/students/{student_id}", headers=admin_auth_headers)
    assert del_res.status_code == 204


# ==============================================================================
# 6. STALE JWT ROLE CLAIM VS DATABASE ROLE
# ==============================================================================

def test_stale_jwt_role_claim_cannot_bypass_academic_rbac(
    client: TestClient,
    test_user: User,
):
    # test_user has FACULTY role in DB
    # Forged/stale token claims role="ADMIN"
    forged_admin_token = create_access_token(subject=test_user.id, role="ADMIN")
    headers = {"Authorization": f"Bearer {forged_admin_token}"}

    # Attempt admin-only academic action (create subject)
    res = client.post(
        "/api/subjects/",
        json={"name": "Exploit Subject", "code": "EXP101"},
        headers=headers,
    )
    # Must be 403 Forbidden because backend verifies the database user record role (FACULTY)
    assert res.status_code == 403
    assert "Insufficient permissions" in res.json()["detail"]
