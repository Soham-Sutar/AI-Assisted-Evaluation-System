from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.answer_sheet import ProcessingStatus
from app.schemas.answer_page import AnswerPageRead
from app.schemas.answer import AnswerRead


class AnswerSheetBase(BaseModel):
    examination_id: str
    student_id: str


class AnswerSheetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    examination_id: str
    student_id: str
    original_filename: str
    page_count: int
    processing_status: ProcessingStatus
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    examination_name: Optional[str] = None
    student_name: Optional[str] = None
    student_register_number: Optional[str] = None
    page_count_actual: Optional[int] = None
    answer_count: Optional[int] = None


class AnswerSheetDetailRead(AnswerSheetRead):
    pages: List[AnswerPageRead] = []
    answers: List[AnswerRead] = []
