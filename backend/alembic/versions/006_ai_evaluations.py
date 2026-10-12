"""create ai evaluations table

Revision ID: 006_ai_evaluations
Revises: 005_faculty_evaluations
Create Date: 2026-10-12 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "006_ai_evaluations"
down_revision: Union[str, None] = "005_faculty_evaluations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create enum if not exists
    op.execute(
        sa.text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_evaluation_status') "
            "THEN CREATE TYPE ai_evaluation_status AS ENUM ('PENDING', 'COMPLETED', 'FAILED'); "
            "END IF; END $$;"
        )
    )
    status_enum = postgresql.ENUM(
        "PENDING",
        "COMPLETED",
        "FAILED",
        name="ai_evaluation_status",
        create_type=False,
    )

    op.create_table(
        "ai_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("answer_id", sa.String(length=36), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="COMPLETED"),
        sa.Column("ai_marks", sa.Float(), nullable=True),
        sa.Column("max_marks", sa.Float(), nullable=False),
        sa.Column("final_ai_score", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("semantic_similarity", sa.Float(), nullable=True),
        sa.Column("keypoint_score", sa.Float(), nullable=True),
        sa.Column("explanation_json", sa.JSON(), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["answer_id"], ["answers.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("ai_marks IS NULL OR ai_marks >= 0", name="chk_ai_eval_marks_positive"),
        sa.CheckConstraint("ai_marks IS NULL OR ai_marks <= max_marks", name="chk_ai_eval_marks_max"),
        sa.CheckConstraint("final_ai_score IS NULL OR final_ai_score >= 0", name="chk_ai_eval_score_positive"),
    )
    op.create_index(op.f("ix_ai_evaluations_id"), "ai_evaluations", ["id"], unique=False)
    op.create_index(op.f("ix_ai_evaluations_answer_id"), "ai_evaluations", ["answer_id"], unique=False)
    op.create_index(op.f("ix_ai_evaluations_status"), "ai_evaluations", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_evaluations_status"), table_name="ai_evaluations")
    op.drop_index(op.f("ix_ai_evaluations_answer_id"), table_name="ai_evaluations")
    op.drop_index(op.f("ix_ai_evaluations_id"), table_name="ai_evaluations")
    op.drop_table("ai_evaluations")
    op.execute(sa.text("DROP TYPE IF EXISTS ai_evaluation_status;"))
