from app.schemas.auth import UserRead, LoginRequest, TokenResponse
from app.schemas.subject import SubjectBase, SubjectCreate, SubjectUpdate, SubjectRead
from app.schemas.faculty_subject import FacultySubjectCreate, FacultySubjectRead
from app.schemas.examination import ExaminationBase, ExaminationCreate, ExaminationUpdate, ExaminationRead
from app.schemas.question import QuestionBase, QuestionCreate, QuestionUpdate, QuestionRead
from app.schemas.student import StudentBase, StudentCreate, StudentUpdate, StudentRead

__all__ = [
    "UserRead",
    "LoginRequest",
    "TokenResponse",
    "SubjectBase",
    "SubjectCreate",
    "SubjectUpdate",
    "SubjectRead",
    "FacultySubjectCreate",
    "FacultySubjectRead",
    "ExaminationBase",
    "ExaminationCreate",
    "ExaminationUpdate",
    "ExaminationRead",
    "QuestionBase",
    "QuestionCreate",
    "QuestionUpdate",
    "QuestionRead",
    "StudentBase",
    "StudentCreate",
    "StudentUpdate",
    "StudentRead",
]
