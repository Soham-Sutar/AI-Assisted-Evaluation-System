import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from sqlalchemy import (
    String,
    Float,
    DateTime,
    JSON,
    ForeignKey,
    CheckConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AIEvaluationStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AIEvaluation(Base):
    __tablename__ = "ai_evaluations"
    __table_args__ = (
        CheckConstraint("ai_marks IS NULL OR ai_marks >= 0", name="chk_ai_eval_marks_positive"),
        CheckConstraint("ai_marks IS NULL OR ai_marks <= max_marks", name="chk_ai_eval_marks_max"),
        CheckConstraint("final_ai_score IS NULL OR final_ai_score >= 0", name="chk_ai_eval_score_positive"),
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
    status: Mapped[AIEvaluationStatus] = mapped_column(
        SQLEnum(AIEvaluationStatus, name="ai_evaluation_status", native_enum=True),
        default=AIEvaluationStatus.COMPLETED,
        nullable=False,
        index=True,
    )
    ai_marks: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    max_marks: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    final_ai_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    semantic_similarity: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    keypoint_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    explanation_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    answer: Mapped["Answer"] = relationship(
        "Answer",
        back_populates="ai_evaluations",
    )

    def __repr__(self) -> str:
        return f"<AIEvaluation {self.id} [Answer: {self.answer_id}, Status: {self.status}, Marks: {self.ai_marks}/{self.max_marks}]>"
