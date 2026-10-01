import uuid
from enum import Enum
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Float,
    Text,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class SegmentationStatus(str, Enum):
    DETECTED = "DETECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CORRECTED = "CORRECTED"
    VERIFIED = "VERIFIED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (
        UniqueConstraint("answer_sheet_id", "question_id", name="uq_answer_sheet_question"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    answer_sheet_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("answer_sheets.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("questions.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    answer_page_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("answer_pages.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    crop_image_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    ocr_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    corrected_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    ocr_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    segmentation_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    status: Mapped[SegmentationStatus] = mapped_column(
        SQLEnum(SegmentationStatus, name="segmentation_status", native_enum=True),
        default=SegmentationStatus.DETECTED,
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
    answer_sheet: Mapped["AnswerSheet"] = relationship(
        "AnswerSheet",
        back_populates="answers",
    )
    question: Mapped["Question"] = relationship(
        "Question",
        back_populates="answers",
    )
    page: Mapped[Optional["AnswerPage"]] = relationship(
        "AnswerPage",
    )

    def __repr__(self) -> str:
        return f"<Answer {self.id} [Sheet: {self.answer_sheet_id}, Q: {self.question_id}, Status: {self.status}]>"
