from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_roles
from app.models.user import User, UserRole
from app.services.audit_service import get_audit_logs

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


@router.get("")
@router.get("/")
def list_logs(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    user_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Search and inspect audit logs."""
    return get_audit_logs(
        action=action,
        entity_type=entity_type,
        user_id=user_id,
        entity_id=entity_id,
        limit=limit,
        offset=offset,
    )
