from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.assignment import AssignmentType, AssignmentStatus


class AssignmentCreate(BaseModel):
    answer_id: str = Field(..., min_length=1, description="ID of the answer to assign")
    faculty_id: str = Field(..., min_length=1, description="ID of the faculty user to assign to")
    assignment_type: AssignmentType = AssignmentType.PRIMARY


class AssignmentUpdate(BaseModel):
    status: Optional[AssignmentStatus] = None
    faculty_id: Optional[str] = Field(None, min_length=1, description="New faculty ID for reassignment")


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    answer_id: str
    faculty_id: str
    assignment_type: AssignmentType
    status: AssignmentStatus
    assigned_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Enriched fields (populated by router)
    faculty_name: Optional[str] = None
    faculty_email: Optional[str] = None
    question_number: Optional[int] = None
    examination_name: Optional[str] = None
    subject_name: Optional[str] = None
    student_register_number: Optional[str] = None
