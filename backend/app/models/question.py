import uuid
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Integer,
    Float,
    Text,
    DateTime,
    JSON,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint(
            "examination_id",
            "question_number",
            name="uq_question_exam_number",
        ),
        CheckConstraint("max_marks > 0", name="ck_question_max_marks"),
        CheckConstraint("question_number > 0", name="ck_question_number"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    examination_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("examinations.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    question_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    max_marks: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    model_answer_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    rubric_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
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
    examination: Mapped["Examination"] = relationship(
        "Examination",
        back_populates="questions",
    )

    def __repr__(self) -> str:
        return f"<Question Q{self.question_number} (Max: {self.max_marks} marks)>"
