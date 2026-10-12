from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.review_case import ReviewTriggerType, ReviewStatus, ReviewPriority


class ReviewCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    answer_id: str
    faculty_evaluation_id: Optional[str] = None
    ai_evaluation_id: Optional[str] = None
    trigger_type: ReviewTriggerType
    discrepancy_value: Optional[float] = None
    discrepancy_amount: Optional[float] = None
    priority: ReviewPriority
    status: ReviewStatus
    note: Optional[str] = None
    trigger_reason: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewer_marks: Optional[float] = None
    reviewer_comments: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    # Enriched fields
    question_number: Optional[int] = None
    question_text: Optional[str] = None
    max_marks: Optional[float] = None
    faculty_marks: Optional[float] = None
    ai_marks: Optional[float] = None
    faculty_name: Optional[str] = None


class DiscrepancyCheckResponse(BaseModel):
    answer_id: str
    faculty_marks: float
    ai_marks: float
    max_marks: float
    absolute_difference: float
    relative_difference: float
    absolute_threshold: float
    relative_threshold: float
    is_discrepant: bool
    discrepancy_detected: bool
    has_discrepancy: bool = False
    discrepancy_amount: float = 0.0
    review_case: Optional[ReviewCaseRead] = None
    message: str
