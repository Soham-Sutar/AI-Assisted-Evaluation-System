from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationCreate(BaseModel):
    assignment_id: Optional[str] = Field(None, description="ID of the assignment being evaluated")
    answer_id: Optional[str] = Field(None, description="ID of the answer being evaluated")
    marks_awarded: Optional[float] = Field(None, ge=0, description="Marks awarded to the answer")
    comments: Optional[str] = Field(None, description="Optional feedback/comments from the evaluator")
    submit: bool = Field(default=True, description="Whether to submit or save as draft")


class EvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    answer_id: str
    faculty_id: str
    assignment_id: str
    marks_awarded: float
    max_marks: float
    comments: Optional[str]
    submitted_at: datetime
    version: int

    # Enriched fields
    faculty_name: Optional[str] = None
    question_number: Optional[int] = None
    examination_name: Optional[str] = None
    register_number: Optional[str] = None
    student_name: Optional[str] = None
    ai_status: Optional[str] = None
    ai_marks: Optional[float] = None

