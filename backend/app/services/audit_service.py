"""Audit logging. Never pass passwords/tokens/secrets in metadata (sanitised defensively)."""
import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog

_FORBIDDEN = {"password", "password_hash", "token", "access_token", "secret", "jwt", "authorization"}


def _clean(meta: dict | None) -> dict | None:
    if not meta:
        return None
    out = {}
    for k, v in meta.items():
        if k.lower() in _FORBIDDEN:
            continue
        out[k] = _clean(v) if isinstance(v, dict) else (str(v) if isinstance(v, uuid.UUID) else v)
    return out


def log_action(db: Session, user_id, action: str, entity_type: str | None = None, entity_id=None,
               metadata: dict | None = None, commit: bool = False) -> AuditLog:
    entry = AuditLog(user_id=user_id, action=action, entity_type=entity_type,
                     entity_id=str(entity_id) if entity_id is not None else None, metadata_json=_clean(metadata))
    db.add(entry)
    if commit:
        db.commit()
    return entry
