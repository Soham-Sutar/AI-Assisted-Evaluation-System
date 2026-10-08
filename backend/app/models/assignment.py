import uuid
from enum import Enum
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class AssignmentType(str, Enum):
    PRIMARY = "PRIMARY"
    REEVALUATION = "REEVALUATION"
    REVIEW = "REVIEW"


class AssignmentStatus(str, Enum):
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REASSIGNED = "REASSIGNED"
    CANCELLED = "CANCELLED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        # An answer can only have one active (non-cancelled/non-reassigned) assignment per faculty
        UniqueConstraint(
            "answer_id",
            "faculty_id",
            "assignment_type",
            name="uq_assignment_answer_faculty_type",
        ),
        Index("ix_assignments_faculty_status", "faculty_id", "status"),
        Index("ix_assignments_answer_status", "answer_id", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    answer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("answers.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    faculty_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    assignment_type: Mapped[AssignmentType] = mapped_column(
        SQLEnum(AssignmentType, name="assignment_type", native_enum=True),
        default=AssignmentType.PRIMARY,
        nullable=False,
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        SQLEnum(AssignmentStatus, name="assignment_status", native_enum=True),
        default=AssignmentStatus.ASSIGNED,
        nullable=False,
        index=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # Relationships
    answer: Mapped["Answer"] = relationship(
        "Answer",
        back_populates="assignments",
    )
    faculty: Mapped["User"] = relationship(
        "User",
        back_populates="assignments",
    )

    def __repr__(self) -> str:
        return (
            f"<Assignment {self.id} [Answer: {self.answer_id}, "
            f"Faculty: {self.faculty_id}, Status: {self.status}]>"
        )
