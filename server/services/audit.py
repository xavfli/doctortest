"""Audit log helper: records administrative actions for the admin panel."""
from __future__ import annotations

from sqlalchemy.orm import Session

from server.models import AuditLog, User


def record(
    db: Session,
    user: User | None,
    action: str,
    entity: str | None = None,
    entity_id: object | None = None,
    detail: str | None = None,
) -> AuditLog | None:
    """Append an entry to the audit log. Never raises on logging problems.

    A nested transaction keeps a failure here from rolling back the caller's
    pending work (for example a bulk question import).
    """
    entry = AuditLog(
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        detail=detail,
    )
    db.add(entry)
    try:
        db.flush()
    except Exception:  # pragma: no cover - logging must not break the request
        pass
    return entry
