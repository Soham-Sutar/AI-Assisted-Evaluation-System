from fastapi import APIRouter, Depends, HTTPException

from app.ai.embeddings import provider_status
from app.api.deps import admin_only, get_db
from app.models import User
from app.schemas.inputs import SettingsIn
from app.services import settings_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings_view(db=Depends(get_db), _: User = Depends(admin_only)):
    return settings_service.get_effective(db)


@router.put("")
def update(body: SettingsIn, db=Depends(get_db), admin: User = Depends(admin_only)):
    vals = body.model_dump(exclude_none=True)
    try:
        out = settings_service.update_settings(db, vals)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    log_action(db, admin.id, "settings.updated", "Settings", None, vals, commit=True)
    return out


@router.get("/ai-status")
def ai_status(_: User = Depends(admin_only)):
    return provider_status()
