"""Audit logging. Never pass passwords/tokens/secrets in metadata (sanitised defensively)."""
import uuid
import logging
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session

logger = logging.getLogger("evalai.audit")

_FORBIDDEN = {"password", "password_hash", "token", "access_token", "secret", "jwt", "authorization"}


def _clean(meta: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not meta:
        return None
    out = {}
    for k, v in meta.items():
        if k.lower() in _FORBIDDEN:
            continue
        out[k] = _clean(v) if isinstance(v, dict) else (str(v) if isinstance(v, uuid.UUID) else v)
    return out


def log_action(
    db: Session,
    user_id: Optional[str],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
    commit: bool = False,
) -> Optional[Any]:
    clean_meta = _clean(metadata)
    logger.info(
        f"AUDIT_LOG: user={user_id} action={action} entity_type={entity_type} "
        f"entity_id={entity_id} metadata={clean_meta}"
    )

    try:
        from app.models.entities import AuditLog
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            metadata_json=clean_meta,
        )
        db.add(entry)
        if commit:
            db.commit()
        return entry
    except Exception as e:
        logger.debug(f"AuditLog database write skipped: {e}")
        return None
