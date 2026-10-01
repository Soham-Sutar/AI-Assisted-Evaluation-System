"""create academic core tables

Revision ID: 002_create_academic_core_tables
Revises: 001_create_users_table
Create Date: 2026-10-01 14:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002_create_academic_core_tables"
down_revision: Union[str, None] = "001_create_users_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create exam_status enum if not exists
    op.execute(
        sa.text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'exam_status') "
            "THEN CREATE TYPE exam_status AS ENUM ('DRAFT', 'READY', 'PROCESSING', 'EVALUATION', 'REVIEW', 'COMPLETED'); "
            "END IF; END $$;"
        )
    )
    exam_status_enum = postgresql.ENUM(
        "DRAFT",
        "READY",
        "PROCESSING",
        "EVALUATION",
        "REVIEW",
        "COMPLETED",
        name="exam_status",
        create_type=False,
    )

    # 2. Create subjects table
    op.create_table(
        "subjects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_subjects_id"), "subjects", ["id"], unique=False)
    op.create_index(op.f("ix_subjects_code"), "subjects", ["code"], unique=True)

    # 3. Create faculty_subjects table
    op.create_table(
        "faculty_subjects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("faculty_id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["faculty_id"], ["users.id"], ondelete="CASCADE", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("faculty_id", "subject_id", name="uq_faculty_subject"),
    )
    op.create_index(op.f("ix_faculty_subjects_id"), "faculty_subjects", ["id"], unique=False)
    op.create_index(op.f("ix_faculty_subjects_faculty_id"), "faculty_subjects", ["faculty_id"], unique=False)
    op.create_index(op.f("ix_faculty_subjects_subject_id"), "faculty_subjects", ["subject_id"], unique=False)

    # 4. Create examinations table
    op.create_table(
        "examinations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("academic_year", sa.String(length=50), nullable=False),
        sa.Column("semester", sa.String(length=50), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("total_marks", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", exam_status_enum, nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject_id", "name", "academic_year", "semester", name="uq_examination_instance"),
        sa.CheckConstraint("total_marks >= 0", name="ck_examination_total_marks"),
    )
    op.create_index(op.f("ix_examinations_id"), "examinations", ["id"], unique=False)
    op.create_index(op.f("ix_examinations_subject_id"), "examinations", ["subject_id"], unique=False)
    op.create_index(op.f("ix_examinations_status"), "examinations", ["status"], unique=False)

    # 5. Create questions table
    op.create_table(
        "questions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("examination_id", sa.String(length=36), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("max_marks", sa.Float(), nullable=False),
        sa.Column("model_answer_text", sa.Text(), nullable=True),
        sa.Column("rubric_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["examination_id"], ["examinations.id"], ondelete="CASCADE", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("examination_id", "question_number", name="uq_question_exam_number"),
        sa.CheckConstraint("max_marks > 0", name="ck_question_max_marks"),
        sa.CheckConstraint("question_number > 0", name="ck_question_number"),
    )
    op.create_index(op.f("ix_questions_id"), "questions", ["id"], unique=False)
    op.create_index(op.f("ix_questions_examination_id"), "questions", ["examination_id"], unique=False)

    # 6. Create students table
    op.create_table(
        "students",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("register_number", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("division", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("register_number", name="uq_student_register_number"),
    )
    op.create_index(op.f("ix_students_id"), "students", ["id"], unique=False)
    op.create_index(op.f("ix_students_register_number"), "students", ["register_number"], unique=True)
    op.create_index(op.f("ix_students_email"), "students", ["email"], unique=False)


def downgrade() -> None:
    # Drop in reverse order
    op.drop_index(op.f("ix_students_email"), table_name="students")
    op.drop_index(op.f("ix_students_register_number"), table_name="students")
    op.drop_index(op.f("ix_students_id"), table_name="students")
    op.drop_table("students")

    op.drop_index(op.f("ix_questions_examination_id"), table_name="questions")
    op.drop_index(op.f("ix_questions_id"), table_name="questions")
    op.drop_table("questions")

    op.drop_index(op.f("ix_examinations_status"), table_name="examinations")
    op.drop_index(op.f("ix_examinations_subject_id"), table_name="examinations")
    op.drop_index(op.f("ix_examinations_id"), table_name="examinations")
    op.drop_table("examinations")

    op.drop_index(op.f("ix_faculty_subjects_subject_id"), table_name="faculty_subjects")
    op.drop_index(op.f("ix_faculty_subjects_faculty_id"), table_name="faculty_subjects")
    op.drop_index(op.f("ix_faculty_subjects_id"), table_name="faculty_subjects")
    op.drop_table("faculty_subjects")

    op.drop_index(op.f("ix_subjects_code"), table_name="subjects")
    op.drop_index(op.f("ix_subjects_id"), table_name="subjects")
    op.drop_table("subjects")

    op.execute(sa.text("DROP TYPE IF EXISTS exam_status;"))
