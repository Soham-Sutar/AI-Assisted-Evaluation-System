from app.api.auth import router as auth_router
from app.api.subjects import router as subjects_router
from app.api.faculty_subjects import router as faculty_subjects_router
from app.api.examinations import router as examinations_router
from app.api.questions import router as questions_router
from app.api.students import router as students_router
from app.api.answer_sheets import router as answer_sheets_router
from app.api.answers import router as answers_router

__all__ = [
    "auth_router",
    "subjects_router",
    "faculty_subjects_router",
    "examinations_router",
    "questions_router",
    "students_router",
    "answer_sheets_router",
    "answers_router",
]

