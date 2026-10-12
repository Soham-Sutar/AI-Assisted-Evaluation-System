import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String,
    Float,
    DateTime,
    Text,
    ForeignKey,
    CheckConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReviewTriggerType(str, Enum):
    AI_HUMAN_DISCREPANCY = "AI_HUMAN_DISCREPANCY"
    LOW_AI_CONFIDENCE = "LOW_AI_CONFIDENCE"
    LOW_OCR_CONFIDENCE = "LOW_OCR_CONFIDENCE"
    SEGMENTATION_ERROR = "SEGMENTATION_ERROR"
    MANUAL_FLAG = "MANUAL_FLAG"


class ReviewStatus(str, Enum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class ReviewPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ReviewCase(Base):
    __tablename__ = "review_cases"
    __table_args__ = (
        CheckConstraint(
            "discrepancy_value IS NULL OR discrepancy_value >= 0",
            name="chk_review_case_discrepancy_positive",
        ),
        CheckConstraint(
            "reviewer_marks IS NULL OR reviewer_marks >= 0",
            name="chk_review_case_reviewer_marks_positive",
        ),
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
    faculty_evaluation_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("evaluations.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    ai_evaluation_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("ai_evaluations.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    trigger_type: Mapped[ReviewTriggerType] = mapped_column(
        SQLEnum(ReviewTriggerType, name="review_trigger_type", native_enum=True),
        nullable=False,
        default=ReviewTriggerType.AI_HUMAN_DISCREPANCY,
        index=True,
    )
    discrepancy_value: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    priority: Mapped[ReviewPriority] = mapped_column(
        SQLEnum(ReviewPriority, name="review_priority", native_enum=True),
        nullable=False,
        default=ReviewPriority.MEDIUM,
        index=True,
    )
    status: Mapped[ReviewStatus] = mapped_column(
        SQLEnum(ReviewStatus, name="review_status", native_enum=True),
        nullable=False,
        default=ReviewStatus.OPEN,
        index=True,
    )
    note: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    reviewer_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    reviewer_marks: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    reviewer_comments: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    answer: Mapped["Answer"] = relationship(
        "Answer",
        back_populates="review_cases",
    )
    faculty_evaluation: Mapped[Optional["Evaluation"]] = relationship(
        "Evaluation",
        foreign_keys=[faculty_evaluation_id],
    )
    ai_evaluation: Mapped[Optional["AIEvaluation"]] = relationship(
        "AIEvaluation",
        foreign_keys=[ai_evaluation_id],
    )
    reviewer: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="reviews",
        foreign_keys=[reviewer_id],
    )

    @property
    def discrepancy_amount(self) -> Optional[float]:
        return self.discrepancy_value

    @property
    def trigger_reason(self) -> Optional[str]:
        return self.note

    @property
    def faculty_marks(self) -> Optional[float]:
        return self.faculty_evaluation.marks_awarded if self.faculty_evaluation else None

    @property
    def ai_marks(self) -> Optional[float]:
        return self.ai_evaluation.ai_marks if self.ai_evaluation else None

    def __repr__(self) -> str:

        return f"<ReviewCase {self.id} [Answer: {self.answer_id}, Status: {self.status}, Trigger: {self.trigger_type}]>"
