"""App settings stored in the database, with defaults from config."""
from __future__ import annotations

from sqlalchemy.orm import Session

from server.core.config import settings
from server.models import AppSetting

DEFAULTS: dict[str, str] = {
    "site_title": "Oilaviy shifokorlik testi",
    "site_subtitle": "1005 ta savol · har bo‘limda 20 ta",
    "allow_registration": "true",
    "questions_per_block": str(settings.QUESTIONS_PER_BLOCK),
    "time_limit_minutes": str(settings.ATTEMPT_TIME_LIMIT_MINUTES),
    "default_pass_percent": "60",
    "support_email": "info@osh.uz",
}


def get_str(db: Session, key: str, default: str | None = None) -> str:
    row = db.get(AppSetting, key)
    if row is not None:
        return row.value
    if default is not None:
        return default
    return DEFAULTS.get(key, "")


def get_bool(db: Session, key: str, default: bool = False) -> bool:
    value = get_str(db, key, str(default).lower())
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def get_int(db: Session, key: str, default: int = 0) -> int:
    try:
        return int(str(get_str(db, key, str(default))).strip())
    except (TypeError, ValueError):
        return default


def get_float(db: Session, key: str, default: float = 0.0) -> float:
    try:
        return float(str(get_str(db, key, str(default))).strip())
    except (TypeError, ValueError):
        return default


def set_value(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value


def all_settings(db: Session) -> dict[str, str]:
    data = dict(DEFAULTS)
    for row in db.query(AppSetting).all():
        data[row.key] = row.value
    return data
