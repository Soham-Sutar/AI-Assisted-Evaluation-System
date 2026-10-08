import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String,
    Float,
    DateTime,
    Text,
    Integer,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Evaluation(Base):
    __tablename__ = "evaluations"
    __table_args__ = (
        UniqueConstraint("answer_id", "faculty_id", "assignment_id", name="uq_evaluation_answer_faculty_assignment"),
        CheckConstraint("marks_awarded >= 0", name="chk_evaluation_marks_positive"),
        CheckConstraint("marks_awarded <= max_marks", name="chk_evaluation_marks_max"),
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
    assignment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("assignments.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    marks_awarded: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    max_marks: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    comments: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    # Relationships
    answer: Mapped["Answer"] = relationship(
        "Answer",
        back_populates="evaluations",
    )
    faculty: Mapped["User"] = relationship(
        "User",
        back_populates="evaluations",
    )
    assignment: Mapped["Assignment"] = relationship(
        "Assignment",
        back_populates="evaluations",
    )

    def __repr__(self) -> str:
        return f"<Evaluation {self.id} [Ans: {self.answer_id}, Marks: {self.marks_awarded}/{self.max_marks}]>"
