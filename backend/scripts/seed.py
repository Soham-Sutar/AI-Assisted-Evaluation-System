"""Seed realistic demo data into PostgreSQL (idempotent). Run: python -m scripts.seed [--sheets]

Creates users, subject, exam, questions (model answers + rubrics), students, and faculty eligibility.
With --sheets it also renders synthetic handwriting-like answer sheets into ./demo_sheets/ (named by register number)
which you can upload through the UI/API.
"""
import os
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.subject import Subject
from app.models.faculty_subject import FacultySubject
from app.models.examination import Examination, ExamStatus
from app.models.question import Question
from app.models.student import Student

USERS = [
    ("Admin User", "admin@example.com", UserRole.ADMIN),
    ("Dr. Anita Rao", "faculty1@example.com", UserRole.FACULTY),
    ("Prof. Vikram Shah", "faculty2@example.com", UserRole.FACULTY),
    ("Dr. Meera Iyer", "faculty3@example.com", UserRole.FACULTY),
    ("Rahul Reviewer", "reviewer@example.com", UserRole.REVIEWER),
]

STUDENTS = [
    ("2022IS001", "Aarav Sharma", "A"),
    ("2022IS002", "Diya Patel", "A"),
    ("2022IS003", "Kabir Singh", "A"),
    ("2022IS004", "Isha Nair", "B"),
    ("2022IS005", "Rohan Gupta", "B"),
    ("2022IS006", "Sneha Reddy", "B"),
]

QUESTIONS = [
    (
        1,
        "Explain process scheduling.",
        10,
        "Process scheduling is the method by which the operating system decides which process runs on the CPU at a given time. "
        "Common algorithms include first come first served, shortest job first, round robin and priority scheduling. "
        "The goal is to maximise CPU utilisation and throughput while minimising waiting time.",
        {
            "criteria": [
                {"description": "Definition: the OS decides which process runs on the CPU", "marks": 3},
                {"description": "Algorithms such as FCFS, SJF, round robin and priority scheduling", "marks": 4},
                {"description": "Goals: CPU utilisation, throughput and minimising waiting time", "marks": 3},
            ]
        },
    ),
    (
        2,
        "Explain deadlock prevention.",
        10,
        "Deadlock prevention ensures that at least one of the four necessary conditions can never hold: mutual exclusion, "
        "hold and wait, no preemption and circular wait. For example, requiring processes to request all resources at once "
        "removes hold and wait, and imposing a global ordering of resources removes circular wait.",
        {
            "criteria": [
                {"description": "Four necessary conditions: mutual exclusion, hold and wait, no preemption, circular wait", "marks": 4},
                {"description": "Prevention means breaking at least one condition", "marks": 3},
                {"description": "Examples: request all resources at once, resource ordering", "marks": 3},
            ]
        },
    ),
    (
        3,
        "Compare paging and segmentation.",
        10,
        "Paging divides memory into fixed size pages and frames, avoiding external fragmentation but causing internal fragmentation. "
        "Segmentation divides memory into variable sized logical segments such as code, stack and data, which matches the "
        "programmer's view but can cause external fragmentation.",
        None,
    ),
]


def get_seed_password_for_role(role: UserRole) -> str:
    """Retrieve seed password from environment configuration for the given role."""
    if role == UserRole.ADMIN:
        pwd = settings.ADMIN_SEED_PASSWORD or os.getenv("ADMIN_SEED_PASSWORD")
    elif role == UserRole.FACULTY:
        pwd = settings.FACULTY_SEED_PASSWORD or os.getenv("FACULTY_SEED_PASSWORD")
    elif role == UserRole.REVIEWER:
        pwd = settings.REVIEWER_SEED_PASSWORD or os.getenv("REVIEWER_SEED_PASSWORD")
    else:
        pwd = None

    if not pwd:
        # Fallback to general DEV_PASSWORD if configured in environment
        pwd = os.getenv("DEV_PASSWORD")

    if not pwd:
        raise ValueError(
            f"Missing configured seed password for role '{role.value}'. "
            f"Please set {role.value}_SEED_PASSWORD in your .env file."
        )
    return pwd


def run(sheets: bool = False):
    db = SessionLocal()
    try:
        users = {}
        for name, email, role in USERS:
            u = db.scalar(select(User).where(User.email == email))
            if not u:
                pwd = get_seed_password_for_role(role)
                u = User(
                    full_name=name,
                    email=email,
                    password_hash=hash_password(pwd),
                    role=role,
                )
                db.add(u)
                db.flush()
                print(f"Created development user: {email} ({role.value})")
            else:
                print(f"Development user already exists (preserving existing password): {email} ({role.value})")
            users[email] = u

        subj = db.scalar(select(Subject).where(Subject.code == "CS304"))
        if not subj:
            subj = Subject(
                name="Operating Systems",
                code="CS304",
                description="Core operating systems concepts",
            )
            db.add(subj)
            db.flush()
            print("Created subject: Operating Systems (CS304)")
        else:
            print("Subject CS304 already exists")

        for email in ("faculty1@example.com", "faculty2@example.com", "faculty3@example.com"):
            f = users[email]
            existing_fs = db.scalar(
                select(FacultySubject).where(
                    FacultySubject.faculty_id == f.id,
                    FacultySubject.subject_id == subj.id,
                )
            )
            if not existing_fs:
                db.add(FacultySubject(faculty_id=f.id, subject_id=subj.id))
                print(f"Assigned faculty {email} to CS304")

        exam = db.scalar(
            select(Examination).where(
                Examination.name == "Internal Assessment 1",
                Examination.subject_id == subj.id,
            )
        )
        if not exam:
            exam = Examination(
                name="Internal Assessment 1",
                academic_year="2026-27",
                semester="5",
                subject_id=subj.id,
                status=ExamStatus.READY,
                total_marks=30,
            )
            db.add(exam)
            db.flush()
            print("Created examination: Internal Assessment 1")
        else:
            print("Examination Internal Assessment 1 already exists")

        for n, text, mx, model, rub in QUESTIONS:
            existing_q = db.scalar(
                select(Question).where(
                    Question.examination_id == exam.id,
                    Question.question_number == n,
                )
            )
            if not existing_q:
                db.add(
                    Question(
                        examination_id=exam.id,
                        question_number=n,
                        question_text=text,
                        max_marks=mx,
                        model_answer_text=model,
                        rubric_json=rub,
                    )
                )
                print(f"Created question {n}")

        for reg, name, div in STUDENTS:
            existing_student = db.scalar(select(Student).where(Student.register_number == reg))
            if not existing_student:
                db.add(
                    Student(
                        register_number=reg,
                        name=name,
                        division=div,
                        email=f"{reg.lower()}@students.example.com",
                    )
                )
                print(f"Created student {reg} ({name})")

        db.commit()
        print("Successfully seeded database with development accounts and initial academic records.")
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

    if sheets:
        from scripts.make_demo_sheets import make
        make()


if __name__ == "__main__":
    run("--sheets" in sys.argv)
