from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.embeddings import provider_status
from app.core.database import get_db
from app.api.deps import require_roles
from app.models.user import User, UserRole
from app.schemas.inputs import SettingsIn
from app.services import settings_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("")
@router.get("/")
def get_settings_view(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Get current effective configuration thresholds."""
    return settings_service.get_effective(db)


@router.put("")
@router.put("/")
def update(
    body: SettingsIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Update runtime configuration thresholds."""
    vals = body.model_dump(exclude_none=True)
    try:
        out = settings_service.update_settings(db, vals)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    log_action(db, admin.id, "settings.updated", "Settings", None, vals, commit=True)
    return out


@router.get("/ai-status")
def ai_status(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Admin: Status of AI embeddings and similarity provider."""
    return provider_status()
