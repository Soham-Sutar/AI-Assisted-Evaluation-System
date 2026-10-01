from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class FacultySubjectCreate(BaseModel):
    faculty_id: str = Field(..., min_length=1)
    subject_id: str = Field(..., min_length=1)


class FacultySubjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    faculty_id: str
    subject_id: str
    created_at: datetime
    faculty_name: Optional[str] = None
    faculty_email: Optional[str] = None
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
