from app.core.database import Base
from app.models.user import User, UserRole
from app.models.subject import Subject
from app.models.faculty_subject import FacultySubject
from app.models.examination import Examination, ExamStatus
from app.models.question import Question
from app.models.student import Student
from app.models.answer_sheet import AnswerSheet, ProcessingStatus
from app.models.answer_page import AnswerPage
from app.models.answer import Answer, SegmentationStatus
from app.models.assignment import Assignment, AssignmentType, AssignmentStatus
from app.models.evaluation import Evaluation
from app.models.ai_evaluation import AIEvaluation, AIEvaluationStatus
from app.models.review_case import (
    ReviewCase,
    ReviewTriggerType,
    ReviewStatus,
    ReviewPriority,
)

__all__ = [
    "Base",
    "User",
    "UserRole",
    "Subject",
    "FacultySubject",
    "Examination",
    "ExamStatus",
    "Question",
    "Student",
    "AnswerSheet",
    "ProcessingStatus",
    "AnswerPage",
    "Answer",
    "SegmentationStatus",
    "Assignment",
    "AssignmentType",
    "AssignmentStatus",
    "Evaluation",
    "AIEvaluation",
    "AIEvaluationStatus",
    "ReviewCase",
    "ReviewTriggerType",
    "ReviewStatus",
    "ReviewPriority",
]

