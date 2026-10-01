import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FacultySubject(Base):
    __tablename__ = "faculty_subjects"
    __table_args__ = (
        UniqueConstraint("faculty_id", "subject_id", name="uq_faculty_subject"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    faculty_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("subjects.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    faculty: Mapped["User"] = relationship(
        "User",
        back_populates="faculty_subjects",
    )
    subject: Mapped["Subject"] = relationship(
        "Subject",
        back_populates="faculty_assignments",
    )

    def __repr__(self) -> str:
        return f"<FacultySubject faculty_id={self.faculty_id} subject_id={self.subject_id}>"
