"""Runtime-configurable thresholds: in-memory runtime override with fallback to environment defaults."""
from typing import Any, Dict
from app.core.config import get_settings

KEYS = {
    "review_absolute_threshold": float,
    "review_relative_threshold": float,
    "review_mode": str,
    "ai_low_confidence": float,
    "blind_evaluation": bool,
}

_RUNTIME_OVERRIDES: Dict[str, Any] = {}


def _coerce(key: str, raw: Any):
    t = KEYS[key]
    if t is bool:
        return str(raw).lower() in ("1", "true", "yes", "on")
    return t(raw)


def get_effective(db: Any = None) -> dict:
    s = get_settings()
    out = {k: getattr(s, k) for k in KEYS}
    for k, v in _RUNTIME_OVERRIDES.items():
        if k in KEYS:
            out[k] = _coerce(k, v)
    return out


def update_settings(db: Any, values: dict) -> dict:
    for k, v in values.items():
        if k not in KEYS:
            raise ValueError(f"Unknown setting {k}")
        if k == "review_mode" and v not in ("absolute", "relative", "either"):
            raise ValueError("review_mode must be absolute, relative or either")
        if k in ("review_absolute_threshold", "review_relative_threshold", "ai_low_confidence") and float(v) < 0:
            raise ValueError(f"{k} must be >= 0")
        _RUNTIME_OVERRIDES[k] = v
    return get_effective(db)
