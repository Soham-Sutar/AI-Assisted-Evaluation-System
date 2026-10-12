import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import admin_only, get_db
from app.models import AnswerSheet, Examination, Question, Student, User
from app.services import result_service
from app.services.audit_service import log_action
from app.services.storage_service import get_storage

router = APIRouter(prefix="/api/exams", tags=["results"])


def _exam(db, exam_id):
    e = db.get(Examination, exam_id)
    if not e:
        raise HTTPException(404, "Examination not found")
    return e


def _live(db, exam):
    studs = db.scalars(select(Student).join(AnswerSheet, AnswerSheet.student_id == Student.id)
                       .where(AnswerSheet.examination_id == exam.id).distinct().order_by(Student.register_number))
    return [result_service.student_result(db, exam, s) for s in studs]


@router.get("/{exam_id}/results")
def results(exam_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    """Computed live from stored evaluations/reviews (so it is always consistent with the DB)."""
    exam = _exam(db, exam_id)
    qs = db.scalars(select(Question).where(Question.examination_id == exam_id).order_by(Question.question_number))
    return {"exam": {"id": str(exam.id), "name": exam.name, "status": exam.status},
            "questions": [{"question_number": q.question_number, "max_marks": q.max_marks} for q in qs],
            "results": _live(db, exam)}


@router.get("/{exam_id}/students/{student_id}/result")
def student_result(exam_id: uuid.UUID, student_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    exam, st = _exam(db, exam_id), db.get(Student, student_id)
    if not st:
        raise HTTPException(404, "Student not found")
    return result_service.student_result(db, exam, st)


@router.post("/{exam_id}/calculate-results")
def calculate(exam_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    _exam(db, exam_id)
    return {"results": result_service.calculate_results(db, exam_id, admin.id)}


@router.get("/{exam_id}/results/export.csv")
def export_csv(exam_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    exam = _exam(db, exam_id)
    data = _live(db, exam)
    qnums = sorted({q["question_number"] for r in data for q in r["questions"]})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["register_number", "name", *[f"Q{n}" for n in qnums], "total", "maximum", "percentage", "status", "reviewed_answers"])
    for r in data:
        by = {q["question_number"]: q["marks"] for q in r["questions"]}
        w.writerow([r["register_number"], r["name"], *["" if by.get(n) is None else by[n] for n in qnums], r["total_marks"],
                    r["maximum_marks"], r["percentage"], r["status"], r["reviewed_answers"]])
    content = buf.getvalue()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    name = f"results_{str(exam_id)[:8]}_{stamp}.csv"
    (get_storage().category_dir("exports") / name).write_text(content, encoding="utf-8")
    log_action(db, admin.id, "results.exported", "Examination", exam_id, {"file": name, "rows": len(data)}, commit=True)
    return Response(content, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})
