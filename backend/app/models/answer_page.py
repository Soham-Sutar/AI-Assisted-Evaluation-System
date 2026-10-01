import uuid
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Integer,
    Float,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AnswerPage(Base):
    __tablename__ = "answer_pages"
    __table_args__ = (
        UniqueConstraint("answer_sheet_id", "page_number", name="uq_answerpage_sheet_pagenum"),
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
    page_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    image_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    processed_image_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    ocr_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    ocr_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="PROCESSED",
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    width: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    height: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    answer_sheet: Mapped["AnswerSheet"] = relationship(
        "AnswerSheet",
        back_populates="pages",
    )

    def __repr__(self) -> str:
        return f"<AnswerPage Sheet={self.answer_sheet_id} P{self.page_number}>"
