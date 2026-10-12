"""Subjects, examinations, questions, model answers."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import admin_only, admin_or_reviewer, any_user, get_db, question_dict
from app.models import Answer, AnswerSheet, Examination, Question, Role, Student, Subject, User
from app.schemas.inputs import ExamIn, ModelAnswerIn, QuestionIn, SubjectIn
from app.services.audit_service import log_action

router = APIRouter(prefix="/api", tags=["academic"])


def subject_dict(s: Subject) -> dict:
    return {"id": str(s.id), "name": s.name, "code": s.code, "description": s.description}


def exam_dict(db: Session, e: Examination, detail: bool = False) -> dict:
    d = {"id": str(e.id), "name": e.name, "academic_year": e.academic_year, "semester": e.semester,
         "subject_id": str(e.subject_id), "subject_name": e.subject.name, "subject_code": e.subject.code,
         "exam_date": e.exam_date.isoformat() if e.exam_date else None, "total_marks": e.total_marks,
         "status": e.status, "question_count": len(e.questions)}
    if detail:
        d["sheet_count"] = db.scalar(select(func.count(AnswerSheet.id)).where(AnswerSheet.examination_id == e.id))
        d["answer_count"] = db.scalar(select(func.count(Answer.id)).join(Question, Question.id == Answer.question_id)
                                      .where(Question.examination_id == e.id))
    return d


# ---- subjects
@router.get("/subjects")
def list_subjects(db: Session = Depends(get_db), _: User = Depends(any_user)):
    return [subject_dict(s) for s in db.scalars(select(Subject).order_by(Subject.name))]


@router.post("/subjects", status_code=201)
def create_subject(body: SubjectIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    s = Subject(**body.model_dump())
    db.add(s)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Subject code already exists")
    log_action(db, admin.id, "subject.created", "Subject", s.id, {"code": s.code})
    db.commit()
    return subject_dict(s)


@router.put("/subjects/{subject_id}")
def update_subject(subject_id: uuid.UUID, body: SubjectIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    s = db.get(Subject, subject_id)
    if not s:
        raise HTTPException(404, "Subject not found")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    try:
        log_action(db, admin.id, "subject.updated", "Subject", s.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Subject code already exists")
    return subject_dict(s)


@router.delete("/subjects/{subject_id}", status_code=204)
def delete_subject(subject_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    s = db.get(Subject, subject_id)
    if not s:
        raise HTTPException(404, "Subject not found")
    if db.scalar(select(Examination.id).where(Examination.subject_id == s.id).limit(1)):
        raise HTTPException(409, "Subject is used by an examination and cannot be deleted")
    log_action(db, admin.id, "subject.deleted", "Subject", s.id, {"code": s.code})
    db.delete(s)
    db.commit()


# ---- exams
@router.get("/exams")
def list_exams(db: Session = Depends(get_db), _: User = Depends(admin_or_reviewer)):
    return [exam_dict(db, e) for e in db.scalars(select(Examination).order_by(Examination.created_at.desc()))]


@router.post("/exams", status_code=201)
def create_exam(body: ExamIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    if not db.get(Subject, body.subject_id):
        raise HTTPException(422, "Subject does not exist")
    e = Examination(name=body.name, academic_year=body.academic_year, semester=body.semester,
                    subject_id=body.subject_id, exam_date=body.exam_date, status=body.status or "DRAFT", total_marks=0)
    db.add(e)
    db.flush()
    log_action(db, admin.id, "exam.created", "Examination", e.id, {"name": e.name})
    db.commit()
    db.refresh(e)
    return exam_dict(db, e, True)


@router.get("/exams/{exam_id}")
def get_exam(exam_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(admin_or_reviewer)):
    e = db.get(Examination, exam_id)
    if not e:
        raise HTTPException(404, "Examination not found")
    return exam_dict(db, e, True)


@router.put("/exams/{exam_id}")
def update_exam(exam_id: uuid.UUID, body: ExamIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    e = db.get(Examination, exam_id)
    if not e:
        raise HTTPException(404, "Examination not found")
    if not db.get(Subject, body.subject_id):
        raise HTTPException(422, "Subject does not exist")
    if body.subject_id != e.subject_id and db.scalar(select(AnswerSheet.id).where(AnswerSheet.examination_id == e.id).limit(1)):
        raise HTTPException(409, "Cannot change subject after answer sheets were uploaded")
    e.name, e.academic_year, e.semester, e.subject_id, e.exam_date = (body.name, body.academic_year, body.semester,
                                                                      body.subject_id, body.exam_date)
    if body.status:
        e.status = body.status
    log_action(db, admin.id, "exam.updated", "Examination", e.id, {"status": e.status})
    db.commit()
    db.refresh(e)
    return exam_dict(db, e, True)


# ---- questions
def _sync_total(e: Examination):
    e.total_marks = sum(q.max_marks for q in e.questions)


@router.get("/exams/{exam_id}/questions")
def list_questions(exam_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(admin_or_reviewer)):
    if not db.get(Examination, exam_id):
        raise HTTPException(404, "Examination not found")
    qs = db.scalars(select(Question).where(Question.examination_id == exam_id).order_by(Question.question_number))
    return [question_dict(q) for q in qs]


@router.post("/exams/{exam_id}/questions", status_code=201)
def create_question(exam_id: uuid.UUID, body: QuestionIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    e = db.get(Examination, exam_id)
    if not e:
        raise HTTPException(404, "Examination not found")
    if any(q.question_number == body.question_number for q in e.questions):
        raise HTTPException(409, f"Question {body.question_number} already exists in this examination")
    q = Question(examination_id=e.id, question_number=body.question_number, question_text=body.question_text,
                 max_marks=body.max_marks, model_answer_text=body.model_answer_text,
                 rubric_json=body.rubric.model_dump() if body.rubric else None)
    e.questions.append(q)
    db.flush()
    _sync_total(e)
    log_action(db, admin.id, "question.created", "Question", q.id, {"number": q.question_number, "max": q.max_marks})
    db.commit()
    return question_dict(q)


@router.put("/questions/{question_id}")
def update_question(question_id: uuid.UUID, body: QuestionIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    has_answers = db.scalar(select(Answer.id).where(Answer.question_id == q.id).limit(1))
    if has_answers and (body.question_number != q.question_number or body.max_marks != q.max_marks):
        raise HTTPException(409, "Question number / maximum marks cannot change after answers exist")
    if body.question_number != q.question_number and any(
            x.question_number == body.question_number for x in q.examination.questions):
        raise HTTPException(409, f"Question {body.question_number} already exists")
    q.question_number, q.question_text, q.max_marks = body.question_number, body.question_text, body.max_marks
    q.model_answer_text = body.model_answer_text
    q.rubric_json = body.rubric.model_dump() if body.rubric else None
    db.flush()
    db.refresh(q.examination)
    _sync_total(q.examination)
    log_action(db, admin.id, "question.updated", "Question", q.id)
    db.commit()
    return question_dict(q)


@router.delete("/questions/{question_id}", status_code=204)
def delete_question(question_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    if db.scalar(select(Answer.id).where(Answer.question_id == q.id).limit(1)):
        raise HTTPException(409, "Question has answers and cannot be deleted")
    e = q.examination
    log_action(db, admin.id, "question.deleted", "Question", q.id)
    db.delete(q)
    db.flush()
    db.refresh(e)
    _sync_total(e)
    db.commit()


def _set_model_answer(question_id, body: ModelAnswerIn, db, admin, action):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    if body.rubric and sum(p.marks for p in body.rubric.points) > q.max_marks + 1e-9:
        raise HTTPException(422, "Rubric marks exceed the question's maximum marks")
    q.model_answer_text = body.model_answer_text
    q.rubric_json = body.rubric.model_dump() if body.rubric else None
    log_action(db, admin.id, action, "Question", q.id, {"rubric": bool(body.rubric)})
    db.commit()
    return question_dict(q)


@router.post("/questions/{question_id}/model-answer")
def create_model_answer(question_id: uuid.UUID, body: ModelAnswerIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return _set_model_answer(question_id, body, db, admin, "model_answer.created")


@router.put("/questions/{question_id}/model-answer")
def update_model_answer(question_id: uuid.UUID, body: ModelAnswerIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return _set_model_answer(question_id, body, db, admin, "model_answer.updated")
