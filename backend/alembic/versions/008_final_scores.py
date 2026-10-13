"""create final scores table and answer final marks

Revision ID: 008_final_scores
Revises: 007_review_cases
Create Date: 2026-10-13 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "008_final_scores"
down_revision: Union[str, None] = "007_review_cases"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create enum if not exists
    op.execute(
        sa.text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'final_score_status') "
            "THEN CREATE TYPE final_score_status AS ENUM ('COMPLETE', 'PENDING_REVIEW', 'INCOMPLETE'); "
            "END IF; END $$;"
        )
    )
    status_enum = postgresql.ENUM(
        "COMPLETE",
        "PENDING_REVIEW",
        "INCOMPLETE",
        name="final_score_status",
        create_type=False,
    )

    # 2. Add answer-level final marks columns to answers table
    op.add_column("answers", sa.Column("final_marks", sa.Float(), nullable=True))
    op.add_column("answers", sa.Column("final_marks_source", sa.String(length=20), nullable=True))

    # 3. Create final_scores table
    op.create_table(
        "final_scores",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("examination_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("total_marks", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("maximum_marks", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("percentage", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", status_enum, nullable=False, server_default="INCOMPLETE"),
        sa.Column("breakdown_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["examination_id"],
            ["examinations.id"],
            name="fk_final_scores_examination_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="fk_final_scores_student_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "examination_id", name="uq_final_score_student_exam"),
        sa.CheckConstraint("total_marks >= 0", name="chk_final_score_total_positive"),
        sa.CheckConstraint("maximum_marks >= 0", name="chk_final_score_max_positive"),
        sa.CheckConstraint("percentage >= 0", name="chk_final_score_percentage_positive"),
    )

    op.create_index(op.f("ix_final_scores_id"), "final_scores", ["id"], unique=False)
    op.create_index(op.f("ix_final_scores_examination_id"), "final_scores", ["examination_id"], unique=False)
    op.create_index(op.f("ix_final_scores_student_id"), "final_scores", ["student_id"], unique=False)
    op.create_index(op.f("ix_final_scores_status"), "final_scores", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_final_scores_status"), table_name="final_scores")
    op.drop_index(op.f("ix_final_scores_student_id"), table_name="final_scores")
    op.drop_index(op.f("ix_final_scores_examination_id"), table_name="final_scores")
    op.drop_index(op.f("ix_final_scores_id"), table_name="final_scores")
    op.drop_table("final_scores")

    op.drop_column("answers", "final_marks_source")
    op.drop_column("answers", "final_marks")

    op.execute(sa.text("DROP TYPE IF EXISTS final_score_status;"))
