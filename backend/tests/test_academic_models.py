import pytest
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user import User, UserRole
from app.models.subject import Subject
from app.models.faculty_subject import FacultySubject
from app.models.examination import Examination, ExamStatus
from app.models.question import Question
from app.models.student import Student
from app.core.security import get_password_hash


def test_subject_creation_and_uniqueness(db_session: Session):
    subject = Subject(
        name="Data Structures & Algorithms",
        code="CS201",
        description="Core algorithms and data structures course.",
    )
    db_session.add(subject)
    db_session.flush()

    assert subject.id is not None
    assert subject.code == "CS201"
    assert subject.name == "Data Structures & Algorithms"
    assert subject.created_at is not None
    assert subject.updated_at is not None

    # Duplicate code rejection
    duplicate = Subject(
        name="Different Subject",
        code="CS201",
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_faculty_subject_relationship_and_uniqueness(db_session: Session, test_user: User):
    # test_user has role FACULTY
    subject = Subject(name="Operating Systems", code="CS301")
    db_session.add(subject)
    db_session.flush()

    assignment = FacultySubject(
        faculty_id=test_user.id,
        subject_id=subject.id,
    )
    db_session.add(assignment)
    db_session.flush()

    assert assignment.id is not None
    assert assignment.faculty.email == test_user.email
    assert assignment.subject.code == "CS301"

    # Traversal from User and Subject
    db_session.refresh(test_user)
    db_session.refresh(subject)
    assert len(test_user.faculty_subjects) >= 1
    assert any(fs.subject_id == subject.id for fs in test_user.faculty_subjects)
    assert len(subject.faculty_assignments) == 1

    # Duplicate assignment rejection
    dup_assignment = FacultySubject(
        faculty_id=test_user.id,
        subject_id=subject.id,
    )
    db_session.add(dup_assignment)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_faculty_subject_cascade_deletion(db_session: Session):
    # Create isolated faculty user and subject
    faculty_user = User(
        email="cascade.faculty@example.com",
        full_name="Cascade Faculty",
        password_hash=get_password_hash("Pass123!"),
        role=UserRole.FACULTY,
    )
    subject = Subject(name="Computer Networks", code="CS401")
    db_session.add_all([faculty_user, subject])
    db_session.flush()

    assignment = FacultySubject(
        faculty_id=faculty_user.id,
        subject_id=subject.id,
    )
    db_session.add(assignment)
    db_session.flush()
    assignment_id = assignment.id

    # Deleting subject cascades to faculty_subjects
    db_session.delete(subject)
    db_session.flush()

    deleted_assignment = db_session.get(FacultySubject, assignment_id)
    assert deleted_assignment is None


def test_examination_creation_and_constraints(db_session: Session):
    subject = Subject(name="Database Systems", code="CS202")
    db_session.add(subject)
    db_session.flush()

    exam = Examination(
        subject_id=subject.id,
        name="Mid-Term Examination",
        academic_year="2025-2026",
        semester="Semester 4",
        exam_date=date(2026, 3, 15),
        total_marks=50.0,
        status=ExamStatus.DRAFT,
    )
    db_session.add(exam)
    db_session.flush()

    assert exam.id is not None
    assert exam.status == ExamStatus.DRAFT
    assert exam.subject.code == "CS202"

    # Duplicate examination instance across (subject_id, name, academic_year, semester)
    dup_exam = Examination(
        subject_id=subject.id,
        name="Mid-Term Examination",
        academic_year="2025-2026",
        semester="Semester 4",
    )
    db_session.add(dup_exam)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_subject_deletion_restricted_when_examinations_exist(db_session: Session):
    subject = Subject(name="Compiler Design", code="CS501")
    db_session.add(subject)
    db_session.flush()

    exam = Examination(
        subject_id=subject.id,
        name="Final Examination",
        academic_year="2025-2026",
        semester="Semester 5",
        total_marks=100.0,
    )
    db_session.add(exam)
    db_session.flush()

    # Deleting subject with existing examination must be restricted
    db_session.delete(subject)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_question_creation_and_rubric_json(db_session: Session):
    subject = Subject(name="Software Engineering", code="CS303")
    db_session.add(subject)
    db_session.flush()

    exam = Examination(
        subject_id=subject.id,
        name="Unit Test 1",
        academic_year="2025-2026",
        semester="Semester 3",
        total_marks=20.0,
    )
    db_session.add(exam)
    db_session.flush()

    rubric = {
        "points": [
            {"description": "Definition of Agile principles", "marks": 2.0},
            {"description": "Scrum lifecycle explanation", "marks": 3.0},
        ]
    }

    q1 = Question(
        examination_id=exam.id,
        question_number=1,
        question_text="Explain the Agile methodology and Scrum lifecycle.",
        max_marks=5.0,
        model_answer_text="Agile is an iterative development approach...",
        rubric_json=rubric,
    )
    q2 = Question(
        examination_id=exam.id,
        question_number=2,
        question_text="What is a sprint retrospective?",
        max_marks=5.0,
        model_answer_text="A sprint retrospective is held at the end of a sprint...",
        rubric_json=None,
    )
    db_session.add_all([q1, q2])
    db_session.flush()

    assert q1.id is not None
    assert q2.id is not None
    assert q1.rubric_json["points"][0]["marks"] == 2.0
    assert q1.examination.name == "Unit Test 1"

    # Traversal from exam
    db_session.refresh(exam)
    assert len(exam.questions) == 2
    assert exam.questions[0].question_number == 1
    assert exam.questions[1].question_number == 2

    # Duplicate question number in same exam rejection
    dup_q = Question(
        examination_id=exam.id,
        question_number=1,
        question_text="Duplicate Q1 text",
        max_marks=5.0,
    )
    db_session.add(dup_q)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_examination_cascade_deletes_questions(db_session: Session):
    subject = Subject(name="Artificial Intelligence", code="CS601")
    db_session.add(subject)
    db_session.flush()

    exam = Examination(
        subject_id=subject.id,
        name="AI Midterm",
        academic_year="2025-2026",
        semester="Semester 6",
        total_marks=10.0,
    )
    db_session.add(exam)
    db_session.flush()

    q1 = Question(
        examination_id=exam.id,
        question_number=1,
        question_text="Define A* search algorithm.",
        max_marks=10.0,
    )
    db_session.add(q1)
    db_session.flush()
    q1_id = q1.id

    # Delete exam
    db_session.delete(exam)
    db_session.flush()

    # Question should be cascaded and deleted
    deleted_q = db_session.get(Question, q1_id)
    assert deleted_q is None


def test_student_creation_and_uniqueness(db_session: Session):
    student = Student(
        register_number="STU2022IS001",
        name="Ada Lovelace",
        division="A",
        email="ada.lovelace@student.example.com",
    )
    db_session.add(student)
    db_session.flush()

    assert student.id is not None
    assert student.register_number == "STU2022IS001"
    assert student.name == "Ada Lovelace"
    assert student.created_at is not None

    # Duplicate register_number rejection
    dup_student = Student(
        register_number="STU2022IS001",
        name="Different Student",
    )
    db_session.add(dup_student)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
