from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict
from app.models.final_score import FinalScoreStatus


class QuestionScoreBreakdown(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: str
    question_number: int
    question_text: Optional[str] = None
    max_marks: float
    answer_id: Optional[str] = None
    marks_awarded: Optional[float] = None
    source: Optional[str] = None  # "REVIEWER" | "FACULTY" | None
    is_reviewed: bool = False
    review_pending: bool = False
    faculty_marks: Optional[float] = None
    reviewer_marks: Optional[float] = None
    ai_marks: Optional[float] = None


class StudentResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: str
    register_number: str
    name: str
    division: Optional[str] = None
    examination_id: str
    exam_name: Optional[str] = None
    total_marks: float
    maximum_marks: float
    percentage: float
    status: FinalScoreStatus
    reviewed_answers: int
    questions: List[QuestionScoreBreakdown]
    calculated_at: Optional[datetime] = None


class ExamQuestionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    question_number: int
    question_text: str
    max_marks: float


class ExamResultsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    examination_id: str
    exam_name: str
    status: str
    total_marks: float
    questions: List[ExamQuestionSummary]
    results: List[StudentResultResponse]
    total_students: int
    completed_students: int
    pending_review_students: int
    incomplete_students: int
    average_marks: Optional[float] = None


class CalculateResultsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    examination_id: str
    calculated_count: int
    results: List[StudentResultResponse]
    examination_status: str
    message: str
