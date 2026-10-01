import uuid
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
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
    examinations: Mapped[List["Examination"]] = relationship(
        "Examination",
        back_populates="subject",
    )
    faculty_assignments: Mapped[List["FacultySubject"]] = relationship(
        "FacultySubject",
        back_populates="subject",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Subject {self.code}: {self.name}>"
