from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.review_case import ReviewTriggerType, ReviewStatus, ReviewPriority


class ReviewAssignRequest(BaseModel):
    reviewer_id: Optional[str] = None


class ReviewResolveRequest(BaseModel):
    reviewer_marks: float = Field(..., ge=0.0, description="Marks awarded by the reviewer")
    reviewer_comments: str = Field(..., min_length=1, description="Required explanation for the review decision")


class ReviewEscalateRequest(BaseModel):
    comments: Optional[str] = Field(None, description="Optional explanation for escalating the review case")


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
    reviewer_name: Optional[str] = None
    reviewer_marks: Optional[float] = None
    reviewer_comments: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    # Enriched Question & Academic Details
    question_id: Optional[str] = None
    question_number: Optional[int] = None
    question_text: Optional[str] = None
    max_marks: Optional[float] = None
    model_answer_text: Optional[str] = None
    rubric_json: Optional[Any] = None


    # Enriched Faculty Evaluation Details
    faculty_marks: Optional[float] = None
    faculty_comments: Optional[str] = None
    faculty_name: Optional[str] = None
    faculty_submitted_at: Optional[datetime] = None

    # Enriched AI Evaluation Details
    ai_marks: Optional[float] = None
    ai_confidence_score: Optional[float] = None
    ai_semantic_similarity: Optional[float] = None
    ai_keypoint_score: Optional[float] = None
    ai_explanation_json: Optional[Any] = None
    ai_model_name: Optional[str] = None

    # Enriched Answer Details
    crop_image_path: Optional[str] = None
    ocr_text: Optional[str] = None

    # Enriched Student & Examination Details
    student_id: Optional[str] = None
    student_name: Optional[str] = None
    register_number: Optional[str] = None
    student_register_number: Optional[str] = None
    examination_id: Optional[str] = None
    exam_name: Optional[str] = None



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
