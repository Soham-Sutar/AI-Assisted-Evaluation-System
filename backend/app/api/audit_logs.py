import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import admin_only, get_db
from app.models import AuditLog, User

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


@router.get("")
def list_logs(action: str | None = None, entity_type: str | None = None, user_id: uuid.UUID | None = None,
              entity_id: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
              db: Session = Depends(get_db), _: User = Depends(admin_only)):
    q = select(AuditLog)
    if action:
        q = q.where(AuditLog.action.ilike(f"{action}%"))
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if user_id:
        q = q.where(AuditLog.user_id == user_id)
    if entity_id:
        q = q.where(AuditLog.entity_id == entity_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset))
    return {"total": total, "items": [{"id": str(r.id), "action": r.action, "entity_type": r.entity_type,
                                       "entity_id": r.entity_id, "metadata": r.metadata_json,
                                       "user_email": r.user.email if r.user else None,
                                       "created_at": r.created_at.isoformat()} for r in rows]}
