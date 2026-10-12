from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.ai_evaluation import AIEvaluationStatus


class AIEvaluationTrigger(BaseModel):
    force_reevaluate: bool = Field(False, description="Whether to recompute AI evaluation even if completed")


class AIEvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    answer_id: str
    status: AIEvaluationStatus
    ai_marks: Optional[float] = None
    max_marks: float
    final_ai_score: Optional[float] = None
    confidence_score: Optional[float] = None
    semantic_similarity: Optional[float] = None
    keypoint_score: Optional[float] = None
    explanation_json: Optional[Dict[str, Any]] = None
    model_name: str
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
