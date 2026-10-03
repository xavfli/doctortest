"""Admin dashboard statistics, settings and audit log endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.api.deps import require_admin, require_staff
from server.core.database import get_db
from server.models import AuditLog, Question, User
from server.schemas import AdminStats, AuditOut, SettingOut
from server.services import audit, analytics
from server.services.settings import all_settings, set_value

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStats)
def stats(
    db: Session = Depends(get_db), _: User = Depends(require_staff)
) -> AdminStats:
    """Dashboard counters and breakdowns."""
    return analytics.full_stats(db)


@router.get("/settings", response_model=dict)
def read_settings(
    db: Session = Depends(get_db), _: User = Depends(require_staff)
) -> dict:
    return all_settings(db)


@router.put("/settings", response_model=dict)
def write_settings(
    payload: dict, db: Session = Depends(get_db), admin: User = Depends(require_admin)
) -> dict:
    """Update any subset of the editable settings."""
    for key, value in payload.items():
        if not isinstance(value, (str, int, float, bool)):
            continue
        set_value(db, str(key), str(value).lower() if isinstance(value, bool) else str(value))
    audit.record(db, admin, "settings.update", "settings", None, ",".join(payload.keys()))
    db.commit()
    return all_settings(db)


@router.post("/questions/reset-answers", tags=["admin"])
def reset_answers(
    db: Session = Depends(get_db), admin: User = Depends(require_admin)
) -> dict:
    """Clear answer keys from questions that have none (data-quality helper)."""
    from sqlalchemy import update

    result = db.execute(
        update(Question)
        .where(Question.answer_index.is_(None), Question.answer_all.is_(False))
        .values(answer_text=None, notes=None)
    )
    db.flush()
    audit.record(db, admin, "question.reset_answers", "question", None,
                 f"rows={result.rowcount}")
    db.commit()
    return {"affected": int(result.rowcount or 0)}


@router.get("/audit", response_model=list[AuditOut])
def read_audit(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[AuditOut]:
    rows = db.scalars(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    ).all()
    return [AuditOut.model_validate(r) for r in rows]
