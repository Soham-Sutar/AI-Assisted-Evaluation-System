"""Runtime-configurable thresholds: DB override (app_settings) falls back to environment defaults."""
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AppSetting

KEYS = {
    "review_absolute_threshold": float,
    "review_relative_threshold": float,
    "review_mode": str,
    "ai_low_confidence": float,
    "blind_evaluation": bool,
}


def _coerce(key, raw):
    t = KEYS[key]
    if t is bool:
        return str(raw).lower() in ("1", "true", "yes", "on")
    return t(raw)


def get_effective(db: Session) -> dict:
    s = get_settings()
    out = {k: getattr(s, k) for k in KEYS}
    for row in db.query(AppSetting).all():
        if row.key in KEYS:
            out[row.key] = _coerce(row.key, row.value)
    return out


def update_settings(db: Session, values: dict) -> dict:
    for k, v in values.items():
        if k not in KEYS:
            raise ValueError(f"Unknown setting {k}")
        if k == "review_mode" and v not in ("absolute", "relative", "either"):
            raise ValueError("review_mode must be absolute, relative or either")
        if k in ("review_absolute_threshold", "review_relative_threshold", "ai_low_confidence") and float(v) < 0:
            raise ValueError(f"{k} must be >= 0")
        row = db.get(AppSetting, k)
        if row is None:
            db.add(AppSetting(key=k, value=str(v)))
        else:
            row.value = str(v)
    db.commit()
    return get_effective(db)
