from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.examination import ExamStatus


class ExaminationBase(BaseModel):
    subject_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=255)
    academic_year: str = Field(..., min_length=1, max_length=50)
    semester: str = Field(..., min_length=1, max_length=50)
    exam_date: Optional[date] = None
    total_marks: float = Field(default=0.0, ge=0.0)
    status: ExamStatus = ExamStatus.DRAFT


class ExaminationCreate(ExaminationBase):
    pass


class ExaminationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    academic_year: Optional[str] = Field(None, min_length=1, max_length=50)
    semester: Optional[str] = Field(None, min_length=1, max_length=50)
    exam_date: Optional[date] = None
    total_marks: Optional[float] = Field(None, ge=0.0)
    status: Optional[ExamStatus] = None


class ExaminationRead(ExaminationBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
