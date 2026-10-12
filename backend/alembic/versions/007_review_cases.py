"""create review cases table

Revision ID: 007_review_cases
Revises: 006_ai_evaluations
Create Date: 2026-10-12 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "007_review_cases"
down_revision: Union[str, None] = "006_ai_evaluations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create enums if not exist
    op.execute(
        sa.text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'review_trigger_type') "
            "THEN CREATE TYPE review_trigger_type AS ENUM ('AI_HUMAN_DISCREPANCY', 'LOW_AI_CONFIDENCE', 'LOW_OCR_CONFIDENCE', 'SEGMENTATION_ERROR', 'MANUAL_FLAG'); "
            "END IF; END $$;"
        )
    )
    trigger_enum = postgresql.ENUM(
        "AI_HUMAN_DISCREPANCY",
        "LOW_AI_CONFIDENCE",
        "LOW_OCR_CONFIDENCE",
        "SEGMENTATION_ERROR",
        "MANUAL_FLAG",
        name="review_trigger_type",
        create_type=False,
    )

    op.execute(
        sa.text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'review_status') "
            "THEN CREATE TYPE review_status AS ENUM ('OPEN', 'ASSIGNED', 'RESOLVED', 'ESCALATED'); "
            "END IF; END $$;"
        )
    )
    status_enum = postgresql.ENUM(
        "OPEN",
        "ASSIGNED",
        "RESOLVED",
        "ESCALATED",
        name="review_status",
        create_type=False,
    )

    op.execute(
        sa.text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'review_priority') "
            "THEN CREATE TYPE review_priority AS ENUM ('LOW', 'MEDIUM', 'HIGH'); "
            "END IF; END $$;"
        )
    )
    priority_enum = postgresql.ENUM(
        "LOW",
        "MEDIUM",
        "HIGH",
        name="review_priority",
        create_type=False,
    )

    # 2. Create review_cases table
    op.create_table(
        "review_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("answer_id", sa.String(length=36), nullable=False),
        sa.Column("faculty_evaluation_id", sa.String(length=36), nullable=True),
        sa.Column("ai_evaluation_id", sa.String(length=36), nullable=True),
        sa.Column("trigger_type", trigger_enum, nullable=False, server_default="AI_HUMAN_DISCREPANCY"),
        sa.Column("discrepancy_value", sa.Float(), nullable=True),
        sa.Column("priority", priority_enum, nullable=False, server_default="MEDIUM"),
        sa.Column("status", status_enum, nullable=False, server_default="OPEN"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.String(length=36), nullable=True),
        sa.Column("reviewer_marks", sa.Float(), nullable=True),
        sa.Column("reviewer_comments", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["answer_id"], ["answers.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["faculty_evaluation_id"], ["evaluations.id"], onupdate="CASCADE", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ai_evaluation_id"], ["ai_evaluations.id"], onupdate="CASCADE", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], onupdate="CASCADE", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("discrepancy_value IS NULL OR discrepancy_value >= 0", name="chk_review_case_discrepancy_positive"),
        sa.CheckConstraint("reviewer_marks IS NULL OR reviewer_marks >= 0", name="chk_review_case_reviewer_marks_positive"),
    )
    op.create_index(op.f("ix_review_cases_id"), "review_cases", ["id"], unique=False)
    op.create_index(op.f("ix_review_cases_answer_id"), "review_cases", ["answer_id"], unique=False)
    op.create_index(op.f("ix_review_cases_status"), "review_cases", ["status"], unique=False)
    op.create_index(op.f("ix_review_cases_trigger_type"), "review_cases", ["trigger_type"], unique=False)
    op.create_index(op.f("ix_review_cases_reviewer_id"), "review_cases", ["reviewer_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_review_cases_reviewer_id"), table_name="review_cases")
    op.drop_index(op.f("ix_review_cases_trigger_type"), table_name="review_cases")
    op.drop_index(op.f("ix_review_cases_status"), table_name="review_cases")
    op.drop_index(op.f("ix_review_cases_answer_id"), table_name="review_cases")
    op.drop_index(op.f("ix_review_cases_id"), table_name="review_cases")
    op.drop_table("review_cases")
    op.execute(sa.text("DROP TYPE IF EXISTS review_priority;"))
    op.execute(sa.text("DROP TYPE IF EXISTS review_status;"))
    op.execute(sa.text("DROP TYPE IF EXISTS review_trigger_type;"))
