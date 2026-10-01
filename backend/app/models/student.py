import uuid
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("register_number", name="uq_student_register_number"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    register_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    division: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        index=True,
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
    answer_sheets: Mapped[List["AnswerSheet"]] = relationship(
        "AnswerSheet",
        back_populates="student",
    )

    def __repr__(self) -> str:
        return f"<Student {self.register_number}: {self.name}>"

