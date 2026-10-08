"""create faculty assignments table

Revision ID: 004_faculty_assignments
Revises: 003_answer_sheet_processing_tables
Create Date: 2026-10-04 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004_faculty_assignments"
down_revision: Union[str, None] = "003_answer_sheet_processing_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create assignment_type enum
    op.execute(
        sa.text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'assignment_type') "
            "THEN CREATE TYPE assignment_type AS ENUM ('PRIMARY', 'REEVALUATION', 'REVIEW'); "
            "END IF; END $$;"
        )
    )
    assignment_type_enum = postgresql.ENUM(
        "PRIMARY",
        "REEVALUATION",
        "REVIEW",
        name="assignment_type",
        create_type=False,
    )

    # 2. Create assignment_status enum
    op.execute(
        sa.text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'assignment_status') "
            "THEN CREATE TYPE assignment_status AS ENUM ('ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'REASSIGNED', 'CANCELLED'); "
            "END IF; END $$;"
        )
    )
    assignment_status_enum = postgresql.ENUM(
        "ASSIGNED",
        "IN_PROGRESS",
        "COMPLETED",
        "REASSIGNED",
        "CANCELLED",
        name="assignment_status",
        create_type=False,
    )

    # 3. Create assignments table
    op.create_table(
        "assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("answer_id", sa.String(length=36), nullable=False),
        sa.Column("faculty_id", sa.String(length=36), nullable=False),
        sa.Column("assignment_type", assignment_type_enum, nullable=False, server_default="PRIMARY"),
        sa.Column("status", assignment_status_enum, nullable=False, server_default="ASSIGNED"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["answer_id"], ["answers.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["faculty_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("answer_id", "faculty_id", "assignment_type", name="uq_assignment_answer_faculty_type"),
    )
    op.create_index(op.f("ix_assignments_id"), "assignments", ["id"], unique=False)
    op.create_index(op.f("ix_assignments_answer_id"), "assignments", ["answer_id"], unique=False)
    op.create_index(op.f("ix_assignments_faculty_id"), "assignments", ["faculty_id"], unique=False)
    op.create_index(op.f("ix_assignments_status"), "assignments", ["status"], unique=False)
    op.create_index("ix_assignments_faculty_status", "assignments", ["faculty_id", "status"], unique=False)
    op.create_index("ix_assignments_answer_status", "assignments", ["answer_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_assignments_answer_status", table_name="assignments")
    op.drop_index("ix_assignments_faculty_status", table_name="assignments")
    op.drop_index(op.f("ix_assignments_status"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_faculty_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_answer_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_id"), table_name="assignments")
    op.drop_table("assignments")
    op.execute(sa.text("DROP TYPE IF EXISTS assignment_status;"))
    op.execute(sa.text("DROP TYPE IF EXISTS assignment_type;"))
