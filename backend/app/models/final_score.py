import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Float,
    DateTime,
    JSON,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FinalScoreStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PENDING_REVIEW = "PENDING_REVIEW"
    INCOMPLETE = "INCOMPLETE"


class FinalScore(Base):
    __tablename__ = "final_scores"
    __table_args__ = (
        UniqueConstraint("student_id", "examination_id", name="uq_final_score_student_exam"),
        CheckConstraint("total_marks >= 0", name="chk_final_score_total_positive"),
        CheckConstraint("maximum_marks >= 0", name="chk_final_score_max_positive"),
        CheckConstraint("percentage >= 0", name="chk_final_score_percentage_positive"),
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
        ForeignKey("students.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    total_marks: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    maximum_marks: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    status: Mapped[FinalScoreStatus] = mapped_column(
        SQLEnum(FinalScoreStatus, name="final_score_status", native_enum=True),
        nullable=False,
        default=FinalScoreStatus.INCOMPLETE,
        index=True,
    )
    breakdown_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    examination: Mapped["Examination"] = relationship(
        "Examination",
        back_populates="final_scores",
    )
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="final_scores",
    )

    def __repr__(self) -> str:
        return f"<FinalScore {self.id} [Exam: {self.examination_id}, Student: {self.student_id}, Marks: {self.total_marks}/{self.maximum_marks}, Status: {self.status}]>"
