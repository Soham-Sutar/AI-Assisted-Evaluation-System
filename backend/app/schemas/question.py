from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class QuestionBase(BaseModel):
    question_number: int = Field(..., gt=0, description="Sequential question number (must be > 0)")
    question_text: str = Field(..., min_length=1, description="Question statement or prompt")
    max_marks: float = Field(..., gt=0.0, description="Maximum marks for this question (must be > 0)")
    model_answer_text: Optional[str] = None
    rubric_json: Optional[Dict[str, Any]] = None
    rubric: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def harmonize_rubric(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rubric" in data and "rubric_json" not in data:
                data["rubric_json"] = data["rubric"]
            elif "rubric_json" in data and "rubric" not in data:
                data["rubric"] = data["rubric_json"]
        return data


class QuestionCreate(QuestionBase):
    pass


class QuestionUpdate(BaseModel):
    question_number: Optional[int] = Field(None, gt=0)
    question_text: Optional[str] = Field(None, min_length=1)
    max_marks: Optional[float] = Field(None, gt=0.0)
    model_answer_text: Optional[str] = None
    rubric_json: Optional[Dict[str, Any]] = None
    rubric: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def harmonize_rubric(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rubric" in data and "rubric_json" not in data:
                data["rubric_json"] = data["rubric"]
            elif "rubric_json" in data and "rubric" not in data:
                data["rubric"] = data["rubric_json"]
        return data


class QuestionRead(QuestionBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    examination_id: str
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def populate_rubric(self) -> "QuestionRead":
        if self.rubric is None and self.rubric_json is not None:
            self.rubric = self.rubric_json
        return self

