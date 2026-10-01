import uuid
from enum import Enum
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Integer,
    Text,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ProcessingStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AnswerSheet(Base):
    __tablename__ = "answer_sheets"
    __table_args__ = (
        UniqueConstraint("examination_id", "student_id", name="uq_answersheet_exam_student"),
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
    student_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    original_file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    page_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        SQLEnum(ProcessingStatus, name="processing_status", native_enum=True),
        default=ProcessingStatus.UPLOADED,
        nullable=False,
        index=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
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
        back_populates="answer_sheets",
    )
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="answer_sheets",
    )
    pages: Mapped[List["AnswerPage"]] = relationship(
        "AnswerPage",
        back_populates="answer_sheet",
        cascade="all, delete-orphan",
        order_by="AnswerPage.page_number",
    )
    answers: Mapped[List["Answer"]] = relationship(
        "Answer",
        back_populates="answer_sheet",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AnswerSheet {self.id} [Exam: {self.examination_id}, Student: {self.student_id}, Status: {self.processing_status}]>"
