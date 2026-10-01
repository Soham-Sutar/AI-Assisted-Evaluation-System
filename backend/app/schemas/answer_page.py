from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AnswerPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    answer_sheet_id: str
    page_number: int
    image_path: str
    processed_image_path: Optional[str] = None
    ocr_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    status: str
    error_message: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime
