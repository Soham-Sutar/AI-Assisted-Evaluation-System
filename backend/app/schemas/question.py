from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class QuestionBase(BaseModel):
    question_number: int = Field(..., gt=0, description="Sequential question number (must be > 0)")
    question_text: str = Field(..., min_length=1, description="Question statement or prompt")
    max_marks: float = Field(..., gt=0.0, description="Maximum marks for this question (must be > 0)")
    model_answer_text: Optional[str] = None
    rubric_json: Optional[Dict[str, Any]] = None


class QuestionCreate(QuestionBase):
    pass


class QuestionUpdate(BaseModel):
    question_number: Optional[int] = Field(None, gt=0)
    question_text: Optional[str] = Field(None, min_length=1)
    max_marks: Optional[float] = Field(None, gt=0.0)
    model_answer_text: Optional[str] = None
    rubric_json: Optional[Dict[str, Any]] = None


class QuestionRead(QuestionBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    examination_id: str
    created_at: datetime
    updated_at: datetime
