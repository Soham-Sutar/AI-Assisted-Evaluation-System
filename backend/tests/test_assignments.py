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
from app.models.answer import Answer, SegmentationStatus
from app.models.answer_sheet import AnswerSheet, ProcessingStatus
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


def test_auto_assign_unassigned_answers_regression(
    client: TestClient,
    admin_auth_headers: dict,
    faculty_auth_headers: dict,
    academic_setup: dict,
):
    """
    Regression test for auto-assign HTTP 500 NameError on func.count:
    1. Unauthenticated or faculty access rejected.
    2. Invalid examination returns 404.
    3. Uploads an answer sheet that creates unassigned answers.
    4. Admin triggers POST /api/assignments/auto-assign.
    5. Confirms 200 OK and workload counting with func.count succeeds without 500 error.
    6. Verifies assignment is created and mapped to eligible faculty.
    """
    exam = academic_setup["examination"]
    student = academic_setup["students"][0]
    faculty = academic_setup["faculty"]

    # 1. Non-admin forbidden
    unauth_res = client.post("/api/assignments/auto-assign", json={"exam_id": exam.id})
    assert unauth_res.status_code == 401

    faculty_res = client.post(
        "/api/assignments/auto-assign",
        json={"exam_id": exam.id},
        headers=faculty_auth_headers,
    )
    assert faculty_res.status_code == 403

    # 2. Non-existent exam returns 404
    not_found_res = client.post(
        "/api/assignments/auto-assign",
        json={"exam_id": "00000000-0000-0000-0000-000000000000"},
        headers=admin_auth_headers,
    )
    assert not_found_res.status_code == 404

    # 3. Create unassigned answer via upload
    img_bytes = generate_synthetic_answer_sheet_png()
    upload_res = client.post(
        "/api/answer-sheets/",
        data={"examination_id": exam.id, "student_id": student.id},
        files={"file": ("auto_sheet.png", img_bytes, "image/png")},
        headers=admin_auth_headers,
    )
    assert upload_res.status_code == 201
    sheet_id = upload_res.json()["id"]
    answers = upload_res.json()["answers"]
    assert len(answers) >= 1
    target_answer_id = answers[0]["id"]

    # Verify that unapproved segments are safely held in unassigned status
    if answers[0]["status"] == SegmentationStatus.NEEDS_REVIEW.value:
        pre_res = client.post(
            "/api/assignments/auto-assign",
            json={"exam_id": exam.id},
            headers=admin_auth_headers,
        )
        assert pre_res.status_code == 200
        assert any(u["reason"] == "Segmentation requires review before assignment" for u in pre_res.json()["unassigned"])

        # Approve the sheet segments so they become eligible for assignment
        app_res = client.post(
            f"/api/answer-sheets/{sheet_id}/approve-all",
            json={"include_flagged": True},
            headers=admin_auth_headers,
        )
        assert app_res.status_code == 200

    # 4. Trigger auto-assign
    auto_res = client.post(
        "/api/assignments/auto-assign",
        json={"exam_id": exam.id},
        headers=admin_auth_headers,
    )
    assert auto_res.status_code == 200
    data = auto_res.json()
    assert "assigned" in data
    assert data["assigned"] >= 1
    assert data["unassigned"] == []

    # 5. Verify the assignment in database via list endpoint
    list_res = client.get(
        f"/api/assignments/?answer_id={target_answer_id}",
        headers=admin_auth_headers,
    )
    assert list_res.status_code == 200
    assignments = list_res.json()
    assert len(assignments) == 1
    assert assignments[0]["faculty_id"] == faculty.id
    assert assignments[0]["status"] == AssignmentStatus.ASSIGNED.value


def test_question_wise_faculty_allocation_rules(
    client: TestClient,
    admin_auth_headers: dict,
    academic_setup: dict,
    db_session: Session,
):
    """
    Test full suite of question-wise faculty allocation rules:
    1. Every answer for Q1 across multiple students is assigned to the same faculty member.
    2. Every answer for Q2 is assigned to the same faculty member.
    3. Different questions can be assigned to different faculty members.
    4. No question group is split across faculty members.
    5. Ineligible faculty are excluded from auto-assignment.
    6. Re-running auto-assignment is idempotent (no duplicate or redistributed assignments).
    7. Answers for a previously assigned question inherit the question's assigned faculty.
    8. Manual reassignment moves the entire question group together.
    9. Manual creation conflicting with existing question assignment is rejected.
    """
    exam = academic_setup["examination"]
    subject = academic_setup["subject"]
    q1 = academic_setup["questions"][0]
    st1, st2, st3 = academic_setup["students"]

    # 1. Add Q2 to the exam
    q2 = Question(
        examination_id=exam.id,
        question_number=2,
        question_text="Explain Virtual Memory and Paging.",
        max_marks=5.0,
        model_answer_text="Paging, page tables, TLB, demand paging.",
    )
    db_session.add(q2)

    # 2. Add second eligible faculty (eligible for this subject)
    fac2 = User(
        email="faculty2.test@example.com",
        full_name="Dr. Faculty Two",
        password_hash="fakehash",
        role=UserRole.FACULTY,
        is_active=True,
    )
    db_session.add(fac2)
    db_session.flush()
    db_session.add(FacultySubject(faculty_id=fac2.id, subject_id=subject.id))

    # 3. Add an ineligible faculty (active faculty, but NOT mapped to this subject)
    fac_ineligible = User(
        email="faculty.ineligible@example.com",
        full_name="Dr. Ineligible",
        password_hash="fakehash",
        role=UserRole.FACULTY,
        is_active=True,
    )
    db_session.add(fac_ineligible)
    db_session.flush()

    # 4. Create AnswerSheets and Answers for Student 1 and Student 2
    sheet1 = AnswerSheet(
        examination_id=exam.id,
        student_id=st1.id,
        original_filename="st1.png",
        original_file_path="storage/st1.png",
        processing_status=ProcessingStatus.PROCESSED,
    )
    sheet2 = AnswerSheet(
        examination_id=exam.id,
        student_id=st2.id,
        original_filename="st2.png",
        original_file_path="storage/st2.png",
        processing_status=ProcessingStatus.PROCESSED,
    )
    db_session.add_all([sheet1, sheet2])
    db_session.flush()

    ans1_q1 = Answer(answer_sheet_id=sheet1.id, question_id=q1.id, status=SegmentationStatus.VERIFIED)
    ans1_q2 = Answer(answer_sheet_id=sheet1.id, question_id=q2.id, status=SegmentationStatus.VERIFIED)
    ans2_q1 = Answer(answer_sheet_id=sheet2.id, question_id=q1.id, status=SegmentationStatus.VERIFIED)
    ans2_q2 = Answer(answer_sheet_id=sheet2.id, question_id=q2.id, status=SegmentationStatus.VERIFIED)
    db_session.add_all([ans1_q1, ans1_q2, ans2_q1, ans2_q2])
    db_session.commit()

    # 5. Run auto-assign
    res = client.post("/api/assignments/auto-assign", json={"exam_id": exam.id}, headers=admin_auth_headers)
    assert res.status_code == 200
    assert res.json()["assigned"] == 4

    # Fetch all assignments
    list_res = client.get(f"/api/assignments/?exam_id={exam.id}", headers=admin_auth_headers)
    assert list_res.status_code == 200
    assignments = list_res.json()
    assert len(assignments) == 4

    # Group by question number
    q1_assignments = [a for a in assignments if a["question_number"] == 1]
    q2_assignments = [a for a in assignments if a["question_number"] == 2]

    assert len(q1_assignments) == 2
    assert len(q2_assignments) == 2

    # Check 1 & 2: All Q1 assigned to SAME faculty, all Q2 assigned to SAME faculty
    q1_fac_ids = {a["faculty_id"] for a in q1_assignments}
    q2_fac_ids = {a["faculty_id"] for a in q2_assignments}
    assert len(q1_fac_ids) == 1, "All Q1 answers must be assigned to the exact same faculty member"
    assert len(q2_fac_ids) == 1, "All Q2 answers must be assigned to the exact same faculty member"

    q1_fac = list(q1_fac_ids)[0]
    q2_fac = list(q2_fac_ids)[0]

    # Check 3: Different questions assigned to different faculty members
    assert q1_fac != q2_fac, "Q1 and Q2 should be balanced across the two available eligible faculty members"

    # Check 4: Ineligible faculty excluded
    assert fac_ineligible.id not in q1_fac_ids
    assert fac_ineligible.id not in q2_fac_ids

    # Check 5: Idempotency - running auto-assign again creates 0 new assignments and does not alter existing
    res2 = client.post("/api/assignments/auto-assign", json={"exam_id": exam.id}, headers=admin_auth_headers)
    assert res2.status_code == 200
    assert res2.json()["assigned"] == 0

    # Check 6: When student 3 adds answers later, they inherit the established question mapping
    sheet3 = AnswerSheet(
        examination_id=exam.id,
        student_id=st3.id,
        original_filename="st3.png",
        original_file_path="storage/st3.png",
        processing_status=ProcessingStatus.PROCESSED,
    )
    db_session.add(sheet3)
    db_session.flush()
    ans3_q1 = Answer(answer_sheet_id=sheet3.id, question_id=q1.id, status=SegmentationStatus.VERIFIED)
    ans3_q2 = Answer(answer_sheet_id=sheet3.id, question_id=q2.id, status=SegmentationStatus.VERIFIED)
    db_session.add_all([ans3_q1, ans3_q2])
    db_session.commit()

    res3 = client.post("/api/assignments/auto-assign", json={"exam_id": exam.id}, headers=admin_auth_headers)
    assert res3.status_code == 200
    assert res3.json()["assigned"] == 2

    list_res3 = client.get(f"/api/assignments/?exam_id={exam.id}", headers=admin_auth_headers)
    assignments3 = list_res3.json()
    assert len(assignments3) == 6

    q1_all = [a for a in assignments3 if a["question_number"] == 1 and a["status"] == AssignmentStatus.ASSIGNED.value]
    q2_all = [a for a in assignments3 if a["question_number"] == 2 and a["status"] == AssignmentStatus.ASSIGNED.value]
    assert len(q1_all) == 3
    assert len(q2_all) == 3
    assert all(a["faculty_id"] == q1_fac for a in q1_all), "All 3 students' Q1 answers must belong to q1_fac"
    assert all(a["faculty_id"] == q2_fac for a in q2_all), "All 3 students' Q2 answers must belong to q2_fac"

    # Check 7: Manual single assignment conflicting with question-wise rule is rejected
    # Create an extra answer for Q1 with a new student st4
    st4 = Student(
        register_number="CS2026004",
        name="Diana Student",
        division="A",
        email="diana@example.com",
    )
    db_session.add(st4)
    db_session.flush()

    sheet4 = AnswerSheet(
        examination_id=exam.id,
        student_id=st4.id,
        original_filename="st4.png",
        original_file_path="storage/st4.png",
        processing_status=ProcessingStatus.PROCESSED,
    )
    db_session.add(sheet4)
    db_session.flush()
    ans4_q1 = Answer(answer_sheet_id=sheet4.id, question_id=q1.id, status=SegmentationStatus.VERIFIED)
    db_session.add(ans4_q1)
    db_session.commit()

    conflict_create = client.post(
        "/api/assignments/",
        json={"answer_id": ans4_q1.id, "faculty_id": q2_fac, "assignment_type": AssignmentType.PRIMARY.value},
        headers=admin_auth_headers,
    )
    assert conflict_create.status_code == 400
    assert "Question-wise faculty allocation requires" in conflict_create.json()["detail"]

    # Check 8: Manual reassignment of one Q1 answer moves the ENTIRE Q1 question group to the new faculty
    target_q1_assignment = q1_all[0]
    reassign_res = client.post(
        f"/api/assignments/{target_q1_assignment['id']}/reassign",
        json={"faculty_id": q2_fac},
        headers=admin_auth_headers,
    )
    assert reassign_res.status_code == 200

    # Verify that all active Q1 assignments are now mapped to q2_fac (none remain active under q1_fac)
    list_after = client.get(f"/api/assignments/?exam_id={exam.id}&question_number=1", headers=admin_auth_headers)
    q1_active = [a for a in list_after.json() if a["status"] == AssignmentStatus.ASSIGNED.value]
    assert len(q1_active) >= 3
    assert all(a["faculty_id"] == q2_fac for a in q1_active), "All Q1 answers must now be reassigned to q2_fac together"


