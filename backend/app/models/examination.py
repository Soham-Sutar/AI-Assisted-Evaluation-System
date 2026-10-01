import uuid
from enum import Enum
from typing import List, Optional
from datetime import datetime, date, timezone
from sqlalchemy import (
    String,
    Float,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ExamStatus(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    PROCESSING = "PROCESSING"
    EVALUATION = "EVALUATION"
    REVIEW = "REVIEW"
    COMPLETED = "COMPLETED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Examination(Base):
    __tablename__ = "examinations"
    __table_args__ = (
        UniqueConstraint(
            "subject_id",
            "name",
            "academic_year",
            "semester",
            name="uq_examination_instance",
        ),
        CheckConstraint("total_marks >= 0", name="ck_examination_total_marks"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("subjects.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    academic_year: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    semester: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    exam_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    total_marks: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    status: Mapped[ExamStatus] = mapped_column(
        SQLEnum(ExamStatus, name="exam_status", native_enum=True),
        default=ExamStatus.DRAFT,
        nullable=False,
        index=True,
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
    subject: Mapped["Subject"] = relationship(
        "Subject",
        back_populates="examinations",
    )
    questions: Mapped[List["Question"]] = relationship(
        "Question",
        back_populates="examination",
        cascade="all, delete-orphan",
        order_by="Question.question_number",
    )
    answer_sheets: Mapped[List["AnswerSheet"]] = relationship(
        "AnswerSheet",
        back_populates="examination",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Examination {self.name} ({self.academic_year} {self.semester}) [{self.status}]>"
