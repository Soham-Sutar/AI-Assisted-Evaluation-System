"""Seed realistic demo data into PostgreSQL (idempotent). Run:  python -m scripts.seed [--sheets]

Creates users, subject, exam, questions (model answers + rubrics), students, faculty eligibility/availability.
With --sheets it also renders synthetic handwriting-like answer sheets into ./demo_sheets/ (named by register number)
which you then upload through the UI/API - nothing about segmentation or marks is pre-computed."""
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (Examination, FacultyAvailability, FacultySubject, Question, Role, Student, Subject, User)

DEV_PASSWORD = "Password123!"
USERS = [("Admin User", "admin@example.com", Role.ADMIN), ("Dr. Anita Rao", "faculty1@example.com", Role.FACULTY),
         ("Prof. Vikram Shah", "faculty2@example.com", Role.FACULTY), ("Dr. Meera Iyer", "faculty3@example.com", Role.FACULTY),
         ("Rahul Reviewer", "reviewer@example.com", Role.REVIEWER)]
STUDENTS = [("2022IS001", "Aarav Sharma", "A"), ("2022IS002", "Diya Patel", "A"), ("2022IS003", "Kabir Singh", "A"),
            ("2022IS004", "Isha Nair", "B"), ("2022IS005", "Rohan Gupta", "B"), ("2022IS006", "Sneha Reddy", "B")]
QUESTIONS = [
    (1, "Explain process scheduling.", 10,
     "Process scheduling is the method by which the operating system decides which process runs on the CPU at a given time. "
     "Common algorithms include first come first served, shortest job first, round robin and priority scheduling. "
     "The goal is to maximise CPU utilisation and throughput while minimising waiting time.",
     {"points": [{"description": "Definition: the OS decides which process runs on the CPU", "marks": 3},
                 {"description": "Algorithms such as FCFS, SJF, round robin and priority scheduling", "marks": 4},
                 {"description": "Goals: CPU utilisation, throughput and minimising waiting time", "marks": 3}]}),
    (2, "Explain deadlock prevention.", 10,
     "Deadlock prevention ensures that at least one of the four necessary conditions can never hold: mutual exclusion, "
     "hold and wait, no preemption and circular wait. For example, requiring processes to request all resources at once "
     "removes hold and wait, and imposing a global ordering of resources removes circular wait.",
     {"points": [{"description": "Four necessary conditions: mutual exclusion, hold and wait, no preemption, circular wait", "marks": 4},
                 {"description": "Prevention means breaking at least one condition", "marks": 3},
                 {"description": "Examples: request all resources at once, resource ordering", "marks": 3}]}),
    (3, "Compare paging and segmentation.", 10,
     "Paging divides memory into fixed size pages and frames, avoiding external fragmentation but causing internal fragmentation. "
     "Segmentation divides memory into variable sized logical segments such as code, stack and data, which matches the "
     "programmer's view but can cause external fragmentation.", None),
]


def run(sheets: bool = False):
    db = SessionLocal()
    try:
        users = {}
        for name, email, role in USERS:
            u = db.scalar(select(User).where(User.email == email))
            if not u:
                u = User(full_name=name, email=email, password_hash=hash_password(DEV_PASSWORD), role=role)
                db.add(u)
                db.flush()
            users[email] = u
        subj = db.scalar(select(Subject).where(Subject.code == "CS304"))
        if not subj:
            subj = Subject(name="Operating Systems", code="CS304", description="Core operating systems concepts")
            db.add(subj)
            db.flush()
        for email in ("faculty1@example.com", "faculty2@example.com", "faculty3@example.com"):
            f = users[email]
            if not db.get(FacultySubject, (f.id, subj.id)):
                db.add(FacultySubject(faculty_id=f.id, subject_id=subj.id))
            if not db.scalar(select(FacultyAvailability).where(FacultyAvailability.faculty_id == f.id)):
                db.add(FacultyAvailability(faculty_id=f.id, is_available=True, max_active_assignments=40))
        exam = db.scalar(select(Examination).where(Examination.name == "Internal Assessment 1", Examination.subject_id == subj.id))
        if not exam:
            exam = Examination(name="Internal Assessment 1", academic_year="2026-27", semester="5", subject_id=subj.id,
                               status="READY", total_marks=30)
            db.add(exam)
            db.flush()
        for n, text, mx, model, rub in QUESTIONS:
            if not db.scalar(select(Question).where(Question.examination_id == exam.id, Question.question_number == n)):
                db.add(Question(examination_id=exam.id, question_number=n, question_text=text, max_marks=mx,
                                model_answer_text=model, rubric_json=rub))
        for reg, name, div in STUDENTS:
            if not db.scalar(select(Student).where(Student.register_number == reg)):
                db.add(Student(register_number=reg, name=name, division=div, email=f"{reg.lower()}@students.example.com"))
        db.commit()
        print("Seeded users, subject, exam, questions, students.")
    finally:
        db.close()
    if sheets:
        from scripts.make_demo_sheets import make
        make()


if __name__ == "__main__":
    run("--sheets" in sys.argv)
