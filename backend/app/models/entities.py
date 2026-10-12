"""SQLAlchemy 2.x models. Status/role fields are plain strings validated by constants below
(avoids native PG enum migration friction while keeping explicit allowed values)."""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


def uid() -> uuid.UUID:
    return uuid.uuid4()


class Role:
    ADMIN = "ADMIN"
    FACULTY = "FACULTY"
    REVIEWER = "REVIEWER"
    ALL = (ADMIN, FACULTY, REVIEWER)


class ExamStatus:
    ALL = ("DRAFT", "READY", "PROCESSING", "EVALUATION", "REVIEW", "COMPLETED")


class SheetStatus:
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class SegStatus:
    DETECTED = "DETECTED"
    VERIFIED = "VERIFIED"
    NEEDS_CORRECTION = "NEEDS_CORRECTION"
    READY = "READY_FOR_EVALUATION"


class AssignStatus:
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REASSIGNED = "REASSIGNED"
    CANCELLED = "CANCELLED"
    ACTIVE = (ASSIGNED, IN_PROGRESS)


class ReviewStatus:
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


UUIDCol = UUID(as_uuid=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    subjects: Mapped[list["Subject"]] = relationship(secondary="faculty_subjects", back_populates="faculty")
    availability: Mapped["FacultyAvailability | None"] = relationship(back_populates="faculty", uselist=False)


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    faculty: Mapped[list[User]] = relationship(secondary="faculty_subjects", back_populates="subjects")


class FacultySubject(Base):
    __tablename__ = "faculty_subjects"
    faculty_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True)


class Examination(Base):
    __tablename__ = "examinations"
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    academic_year: Mapped[str] = mapped_column(String(20))
    semester: Mapped[str] = mapped_column(String(20))
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), index=True)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_marks: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    subject: Mapped[Subject] = relationship()
    questions: Mapped[list["Question"]] = relationship(back_populates="examination", order_by="Question.question_number",
                                                       cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("examination_id", "question_number"),)
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    examination_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("examinations.id", ondelete="CASCADE"), index=True)
    question_number: Mapped[int] = mapped_column(Integer)
    question_text: Mapped[str] = mapped_column(Text)
    max_marks: Mapped[float] = mapped_column(Float)
    model_answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    rubric_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    examination: Mapped[Examination] = relationship(back_populates="questions")


class Student(Base):
    __tablename__ = "students"
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    register_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    division: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AnswerSheet(Base):
    __tablename__ = "answer_sheets"
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    examination_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("examinations.id"), index=True)
    student_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("students.id"), nullable=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(300))
    original_file_path: Mapped[str] = mapped_column(String(500))
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    processing_status: Mapped[str] = mapped_column(String(20), default="UPLOADED")
    processing_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    examination: Mapped[Examination] = relationship()
    student: Mapped[Student | None] = relationship()
    pages: Mapped[list["AnswerPage"]] = relationship(back_populates="sheet", order_by="AnswerPage.page_number",
                                                     cascade="all, delete-orphan")
    answers: Mapped[list["Answer"]] = relationship(back_populates="sheet", cascade="all, delete-orphan")


class AnswerPage(Base):
    __tablename__ = "answer_pages"
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    answer_sheet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("answer_sheets.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    image_path: Mapped[str] = mapped_column(String(500))
    processed_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    debug_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    markers_json: Mapped[list | None] = mapped_column(JSON, nullable=True)  # detected markers for UI overlay
    deskew_angle: Mapped[float | None] = mapped_column(Float, nullable=True)
    sheet: Mapped[AnswerSheet] = relationship(back_populates="pages")


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (Index("ix_answers_sheet_question", "answer_sheet_id", "question_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    answer_sheet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("answer_sheets.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("students.id"), nullable=True, index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), index=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    debug_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100 (Tesseract scale)
    ocr_status: Mapped[str] = mapped_column(String(20), default="PENDING")  # OK | LOW_CONFIDENCE | FAILED | BLANK | PENDING
    segmentation_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-1
    segmentation_label: Mapped[str | None] = mapped_column(String(10), nullable=True)  # High | Medium | Low
    segmentation_status: Mapped[str] = mapped_column(String(25), default="DETECTED", index=True)
    segmentation_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    sheet: Mapped[AnswerSheet] = relationship(back_populates="answers")
    student: Mapped[Student | None] = relationship()
    question: Mapped[Question] = relationship()


class FacultyAvailability(Base):
    __tablename__ = "faculty_availability"
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    faculty_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    max_active_assignments: Mapped[int] = mapped_column(Integer, default=50)
    current_assignment_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    faculty: Mapped[User] = relationship(back_populates="availability")


class FacultyAssignment(Base):
    __tablename__ = "assignments"
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    answer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("answers.id", ondelete="CASCADE"), index=True)
    faculty_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    assignment_type: Mapped[str] = mapped_column(String(20), default="PRIMARY")
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ASSIGNED", index=True)

    answer: Mapped[Answer] = relationship()
    faculty: Mapped[User] = relationship()


class Evaluation(Base):
    __tablename__ = "evaluations"
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    answer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("answers.id", ondelete="CASCADE"), index=True)
    faculty_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assignments.id"), nullable=True)
    marks_awarded: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_marks: Mapped[float] = mapped_column(Float)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    answer: Mapped[Answer] = relationship()
    faculty: Mapped[User] = relationship()


class AIEvaluation(Base):
    __tablename__ = "ai_evaluations"
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    answer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("answers.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(15), default="COMPLETED")  # COMPLETED | FAILED
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    semantic_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    keypoint_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_ai_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReviewCase(Base):
    __tablename__ = "review_cases"
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    answer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("answers.id", ondelete="CASCADE"), index=True)
    trigger_type: Mapped[str] = mapped_column(String(30))
    discrepancy_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[str] = mapped_column(String(10), default="MEDIUM")
    status: Mapped[str] = mapped_column(String(15), default="OPEN", index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewer_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviewer_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    answer: Mapped[Answer] = relationship()
    reviewer: Mapped[User | None] = relationship()


class FinalScore(Base):
    __tablename__ = "final_scores"
    __table_args__ = (UniqueConstraint("student_id", "examination_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"), index=True)
    examination_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("examinations.id"), index=True)
    total_marks: Mapped[float] = mapped_column(Float)
    maximum_marks: Mapped[float] = mapped_column(Float)
    percentage: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20))  # COMPLETE | PENDING_REVIEW | INCOMPLETE
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    student: Mapped[Student] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUIDCol, primary_key=True, default=uid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    user: Mapped[User | None] = relationship()


class AppSetting(Base):
    """Runtime-editable configuration (discrepancy thresholds etc.)."""
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
