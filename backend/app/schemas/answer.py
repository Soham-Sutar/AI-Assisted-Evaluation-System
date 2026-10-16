from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.answer import SegmentationStatus


class AnswerBase(BaseModel):
    answer_sheet_id: str
    question_id: str
    answer_page_id: Optional[str] = None
    crop_image_path: Optional[str] = None
    ocr_text: Optional[str] = None
    corrected_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    segmentation_confidence: Optional[float] = None
    status: SegmentationStatus = SegmentationStatus.DETECTED


class AnswerCorrectionUpdate(BaseModel):
    corrected_text: Optional[str] = None
    question_id: Optional[str] = None
    status: Optional[SegmentationStatus] = None


class AnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    answer_sheet_id: str
    question_id: str
    answer_page_id: Optional[str] = None
    crop_image_path: Optional[str] = None
    ocr_text: Optional[str] = None
    corrected_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    segmentation_confidence: Optional[float] = None
    status: SegmentationStatus
    created_at: datetime
    updated_at: datetime
    question_number: Optional[int] = None
    question_text: Optional[str] = None
    max_marks: Optional[float] = None

    # Extra enriched fields for frontend views
    has_image: Optional[bool] = False
    extracted_text: Optional[str] = None
    segmentation_status: Optional[str] = None
    ocr_status: Optional[str] = None
    ocr_corrected: Optional[bool] = False
    candidate_code: Optional[str] = None
    examination_name: Optional[str] = None
    subject: Optional[str] = None
    model_answer_text: Optional[str] = None
    rubric: Optional[dict] = None
    my_evaluation: Optional[dict] = None
    ai_evaluation: Optional[dict] = None

