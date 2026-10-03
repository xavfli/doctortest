"""Application configuration loaded from the environment with sane defaults."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
WEB_ROOT = BASE_DIR / "web"
BUILD_ROOT = BASE_DIR / "build"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Runtime settings. Every value can be overridden with an env var."""

    PROJECT_NAME: str = os.getenv("APP_NAME", "OSH Test Platform")
    API_PREFIX: str = "/api"
    VERSION: str = "1.0.0"

    DB_PATH: str = os.getenv("DB_PATH", str(DATA_DIR / "app.db"))
    DB_URL: str = os.getenv("DB_URL", f"sqlite:///{DATA_DIR / 'app.db'}")
    WEB_DIR: Path = WEB_ROOT
    BUILD_DIR: Path = BUILD_ROOT

    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720")
    )

    # Registration is open by default; an admin can close it from the panel.
    ALLOW_REGISTRATION: bool = _flag("ALLOW_REGISTRATION", True)
    DEFAULT_ADMIN_EMAIL: str = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@osh.uz")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin12345")
    DEFAULT_TEACHER_EMAIL: str = os.getenv("DEFAULT_TEACHER_EMAIL", "teacher@osh.uz")
    DEFAULT_TEACHER_PASSWORD: str = os.getenv("DEFAULT_TEACHER_PASSWORD", "teacher12345")

    # Question bank behaviour.
    QUESTIONS_PER_BLOCK: int = int(os.getenv("QUESTIONS_PER_BLOCK", "20"))
    ATTEMPT_TIME_LIMIT_MINUTES: int = int(os.getenv("ATTEMPT_TIME_LIMIT_MINUTES", "30"))

    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "*").split(",")
        if o.strip()
    ]

    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").strip().lower()
    IS_PRODUCTION: bool = ENVIRONMENT == "production"

    # Production means internet-facing; local runs (LANG-agnostic default
    # locale is why this is detected via Python and not the shell).
    @property
    def IS_LOCAL(self) -> bool:
        return not self.IS_PRODUCTION


def audit_production_config() -> list[str]:
    """Return the list of unsafe defaults for a public deployment.

    Returns problems instead of raising: a configuration mistake must be
    loud, but it must never make the whole site unreachable — otherwise a
    stray ENVIRONMENT variable silently breaks logins for every user.
    """
    if not settings.IS_PRODUCTION:
        return []
    problems: list[str] = []
    if settings.SECRET_KEY == "dev-secret-change-me-in-production" or len(
        settings.SECRET_KEY
    ) < 32:
        problems.append(
            "SECRET_KEY hali o‘zgartirilmagan "
            '(python -c "import secrets; print(secrets.token_urlsafe(48))")'
        )
    for label, value in (
        ("DEFAULT_ADMIN_PASSWORD", settings.DEFAULT_ADMIN_PASSWORD),
        ("DEFAULT_TEACHER_PASSWORD", settings.DEFAULT_TEACHER_PASSWORD),
    ):
        if value in {"admin12345", "teacher12345"} or len(value) < 12:
            problems.append(f"{label} kuchsiz yoki standart qiymatda")
    return problems


settings = Settings()
