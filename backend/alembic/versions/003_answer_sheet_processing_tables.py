"""create answer sheet processing tables

Revision ID: 003_answer_sheet_processing_tables
Revises: 002_create_academic_core_tables
Create Date: 2026-10-01 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_answer_sheet_processing_tables"
down_revision: Union[str, None] = "002_create_academic_core_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create enums if not exist
    op.execute(
        sa.text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'processing_status') "
            "THEN CREATE TYPE processing_status AS ENUM ('UPLOADED', 'PROCESSING', 'PROCESSED', 'REVIEW_REQUIRED', 'FAILED'); "
            "END IF; END $$;"
        )
    )
    processing_status_enum = postgresql.ENUM(
        "UPLOADED",
        "PROCESSING",
        "PROCESSED",
        "REVIEW_REQUIRED",
        "FAILED",
        name="processing_status",
        create_type=False,
    )

    op.execute(
        sa.text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'segmentation_status') "
            "THEN CREATE TYPE segmentation_status AS ENUM ('DETECTED', 'NEEDS_REVIEW', 'CORRECTED', 'VERIFIED'); "
            "END IF; END $$;"
        )
    )
    segmentation_status_enum = postgresql.ENUM(
        "DETECTED",
        "NEEDS_REVIEW",
        "CORRECTED",
        "VERIFIED",
        name="segmentation_status",
        create_type=False,
    )

    # 2. Create answer_sheets table
    op.create_table(
        "answer_sheets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("examination_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("original_file_path", sa.String(length=500), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("processing_status", processing_status_enum, nullable=False, server_default="UPLOADED"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["examination_id"], ["examinations.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("examination_id", "student_id", name="uq_answersheet_exam_student"),
    )
    op.create_index(op.f("ix_answer_sheets_id"), "answer_sheets", ["id"], unique=False)
    op.create_index(op.f("ix_answer_sheets_examination_id"), "answer_sheets", ["examination_id"], unique=False)
    op.create_index(op.f("ix_answer_sheets_student_id"), "answer_sheets", ["student_id"], unique=False)
    op.create_index(op.f("ix_answer_sheets_processing_status"), "answer_sheets", ["processing_status"], unique=False)

    # 3. Create answer_pages table
    op.create_table(
        "answer_pages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("answer_sheet_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.String(length=500), nullable=False),
        sa.Column("processed_image_path", sa.String(length=500), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PROCESSED"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["answer_sheet_id"], ["answer_sheets.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("answer_sheet_id", "page_number", name="uq_answerpage_sheet_pagenum"),
    )
    op.create_index(op.f("ix_answer_pages_id"), "answer_pages", ["id"], unique=False)
    op.create_index(op.f("ix_answer_pages_answer_sheet_id"), "answer_pages", ["answer_sheet_id"], unique=False)

    # 4. Create answers table
    op.create_table(
        "answers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("answer_sheet_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("answer_page_id", sa.String(length=36), nullable=True),
        sa.Column("crop_image_path", sa.String(length=500), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("corrected_text", sa.Text(), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("segmentation_confidence", sa.Float(), nullable=True),
        sa.Column("status", segmentation_status_enum, nullable=False, server_default="DETECTED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["answer_sheet_id"], ["answer_sheets.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["answer_page_id"], ["answer_pages.id"], onupdate="CASCADE", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("answer_sheet_id", "question_id", name="uq_answer_sheet_question"),
    )
    op.create_index(op.f("ix_answers_id"), "answers", ["id"], unique=False)
    op.create_index(op.f("ix_answers_answer_sheet_id"), "answers", ["answer_sheet_id"], unique=False)
    op.create_index(op.f("ix_answers_question_id"), "answers", ["question_id"], unique=False)
    op.create_index(op.f("ix_answers_answer_page_id"), "answers", ["answer_page_id"], unique=False)
    op.create_index(op.f("ix_answers_status"), "answers", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_answers_status"), table_name="answers")
    op.drop_index(op.f("ix_answers_answer_page_id"), table_name="answers")
    op.drop_index(op.f("ix_answers_question_id"), table_name="answers")
    op.drop_index(op.f("ix_answers_answer_sheet_id"), table_name="answers")
    op.drop_index(op.f("ix_answers_id"), table_name="answers")
    op.drop_table("answers")

    op.drop_index(op.f("ix_answer_pages_answer_sheet_id"), table_name="answer_pages")
    op.drop_index(op.f("ix_answer_pages_id"), table_name="answer_pages")
    op.drop_table("answer_pages")

    op.drop_index(op.f("ix_answer_sheets_processing_status"), table_name="answer_sheets")
    op.drop_index(op.f("ix_answer_sheets_student_id"), table_name="answer_sheets")
    op.drop_index(op.f("ix_answer_sheets_examination_id"), table_name="answer_sheets")
    op.drop_index(op.f("ix_answer_sheets_id"), table_name="answer_sheets")
    op.drop_table("answer_sheets")

    op.execute(sa.text("DROP TYPE IF EXISTS segmentation_status;"))
    op.execute(sa.text("DROP TYPE IF EXISTS processing_status;"))
