"""Pydantic request schemas (validation at the API boundary)."""
from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    role: str = "FACULTY"
    subject_ids: list[uuid.UUID] = []
    max_active_assignments: int = Field(50, ge=0, le=10000)

    @field_validator("role")
    @classmethod
    def _role(cls, v):
        if v not in ("ADMIN", "FACULTY", "REVIEWER"):
            raise ValueError("role must be ADMIN, FACULTY or REVIEWER")
        return v


class FacultyUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=200)
    is_active: bool | None = None
    subject_ids: list[uuid.UUID] | None = None
    password: str | None = Field(None, min_length=8, max_length=100)


class AvailabilityIn(BaseModel):
    is_available: bool = True
    max_active_assignments: int = Field(50, ge=0, le=10000)


class SubjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=1, max_length=50)
    description: str | None = None


class ExamIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    academic_year: str = Field(min_length=4, max_length=20)
    semester: str = Field(min_length=1, max_length=20)
    subject_id: uuid.UUID
    exam_date: date | None = None
    status: str | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, v):
        if v is not None and v not in ("DRAFT", "READY", "PROCESSING", "EVALUATION", "REVIEW", "COMPLETED"):
            raise ValueError("invalid status")
        return v


class RubricPoint(BaseModel):
    description: str = Field(min_length=2, max_length=500)
    marks: float = Field(gt=0)


class Rubric(BaseModel):
    points: list[RubricPoint] = Field(min_length=1)


class QuestionIn(BaseModel):
    question_number: int = Field(ge=1, le=99)
    question_text: str = Field(min_length=3)
    max_marks: float = Field(gt=0, le=1000)
    model_answer_text: str | None = None
    rubric: Rubric | None = None

    @model_validator(mode="after")
    def _rubric_total(self):
        if self.rubric and sum(p.marks for p in self.rubric.points) > self.max_marks + 1e-9:
            raise ValueError("Rubric marks exceed the question's maximum marks")
        return self


class ModelAnswerIn(BaseModel):
    model_answer_text: str = Field(min_length=3)
    rubric: Rubric | None = None


class StudentIn(BaseModel):
    register_number: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=200)
    division: str | None = Field(None, max_length=20)
    email: EmailStr | None = None


class SheetMap(BaseModel):
    student_id: uuid.UUID


class Region(BaseModel):
    page_number: int = Field(ge=1)
    y_start: int = Field(ge=0)
    y_end: int = Field(ge=1)

    @model_validator(mode="after")
    def _order(self):
        if self.y_end <= self.y_start:
            raise ValueError("y_end must be greater than y_start")
        return self


class ManualSegmentIn(BaseModel):
    question_id: uuid.UUID
    regions: list[Region] = Field(min_length=1)


class AnswerSegmentationIn(BaseModel):
    regions: list[Region] = Field(min_length=1)


class OcrTextIn(BaseModel):
    text: str = Field(max_length=20000)


class ApproveAllIn(BaseModel):
    include_flagged: bool = False


class AutoAssignIn(BaseModel):
    exam_id: uuid.UUID


class ReassignIn(BaseModel):
    faculty_id: uuid.UUID | None = None


class EvaluationIn(BaseModel):
    answer_id: uuid.UUID
    marks_awarded: float | None = None
    comments: str | None = Field(None, max_length=5000)
    submit: bool = False


class EvaluationUpdate(BaseModel):
    marks_awarded: float | None = None
    comments: str | None = Field(None, max_length=5000)
    submit: bool = False


class ReviewAssignIn(BaseModel):
    reviewer_id: uuid.UUID


class ReviewResolveIn(BaseModel):
    reviewer_marks: float
    reviewer_comments: str = Field(min_length=1, max_length=5000)


class ReviewEscalateIn(BaseModel):
    comments: str | None = Field(None, max_length=5000)


class SettingsIn(BaseModel):
    review_absolute_threshold: float | None = Field(None, ge=0)
    review_relative_threshold: float | None = Field(None, ge=0, le=1)
    review_mode: str | None = None
    ai_low_confidence: float | None = Field(None, ge=0, le=1)
    blind_evaluation: bool | None = None
