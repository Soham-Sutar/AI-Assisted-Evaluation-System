"""create faculty evaluations table

Revision ID: 005_faculty_evaluations
Revises: 004_faculty_assignments
Create Date: 2026-10-08 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "005_faculty_evaluations"
down_revision: Union[str, None] = "004_faculty_assignments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("answer_id", sa.String(length=36), nullable=False),
        sa.Column("faculty_id", sa.String(length=36), nullable=False),
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("marks_awarded", sa.Float(), nullable=False),
        sa.Column("max_marks", sa.Float(), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["answer_id"], ["answers.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["faculty_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("answer_id", "faculty_id", "assignment_id", name="uq_evaluation_answer_faculty_assignment"),
        sa.CheckConstraint("marks_awarded >= 0", name="chk_evaluation_marks_positive"),
        sa.CheckConstraint("marks_awarded <= max_marks", name="chk_evaluation_marks_max")
    )
    op.create_index(op.f("ix_evaluations_answer_id"), "evaluations", ["answer_id"], unique=False)
    op.create_index(op.f("ix_evaluations_assignment_id"), "evaluations", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_evaluations_faculty_id"), "evaluations", ["faculty_id"], unique=False)
    op.create_index(op.f("ix_evaluations_id"), "evaluations", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_evaluations_id"), table_name="evaluations")
    op.drop_index(op.f("ix_evaluations_faculty_id"), table_name="evaluations")
    op.drop_index(op.f("ix_evaluations_assignment_id"), table_name="evaluations")
    op.drop_index(op.f("ix_evaluations_answer_id"), table_name="evaluations")
    op.drop_table("evaluations")
