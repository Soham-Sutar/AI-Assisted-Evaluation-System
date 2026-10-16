"""Audit logging. Never pass passwords/tokens/secrets in metadata (sanitised defensively)."""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
from sqlalchemy.orm import Session

logger = logging.getLogger("evalai.audit")

_FORBIDDEN = {"password", "password_hash", "token", "access_token", "secret", "jwt", "authorization"}

_MEMORY_AUDIT_LOGS: List[Dict[str, Any]] = []


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

    entry = {
        "id": str(uuid.uuid4()),
        "user_id": str(user_id) if user_id else None,
        "action": action,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id is not None else None,
        "metadata_json": clean_meta,
        "created_at": datetime.now(timezone.utc),
    }
    _MEMORY_AUDIT_LOGS.insert(0, entry)
    if len(_MEMORY_AUDIT_LOGS) > 1000:
        _MEMORY_AUDIT_LOGS.pop()
    return entry


def get_audit_logs(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    user_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    filtered = _MEMORY_AUDIT_LOGS
    if action:
        filtered = [l for l in filtered if action.lower() in l["action"].lower()]
    if entity_type:
        filtered = [l for l in filtered if l["entity_type"] == entity_type]
    if user_id:
        filtered = [l for l in filtered if l["user_id"] == user_id]
    if entity_id:
        filtered = [l for l in filtered if l["entity_id"] == entity_id]

    total = len(filtered)
    rows = filtered[offset : offset + limit]
    return {
        "total": total,
        "items": [
            {
                "id": r["id"],
                "action": r["action"],
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "metadata": r["metadata_json"],
                "user_email": None,
                "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
            }
            for r in rows
        ],
    }
