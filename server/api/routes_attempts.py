"""Attempt endpoints: start an exam, save progress, submit and review."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.api.deps import get_current_user
from server.core.database import get_db
from server.models import (
    ROLE_ADMIN,
    ROLE_TEACHER,
    STATUS_EXPIRED,
    STATUS_IN_PROGRESS,
    STATUS_SUBMITTED,
    Attempt,
    Exam,
    User,
)
from server.schemas import AttemptOut, AttemptStart, AttemptSubmit, AttemptSummary
from server.services import audit
from server.services.exam_engine import (
    build_attempt,
    expire_stale,
    grade_attempt,
    load_attempt_for_user,
    remaining_seconds,
)
from server.services.settings import get_float, get_int

router = APIRouter(prefix="/attempts", tags=["attempts"])


def _get_attempt(db: Session, attempt_id: int, user: User) -> Attempt:
    attempt = db.get(Attempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Urinish topilmadi")
    if attempt.user_id != user.id and user.role not in (ROLE_ADMIN, ROLE_TEACHER):
        raise HTTPException(status_code=403, detail="Bu urinish sizniki emas")
    return attempt


@router.post("/start", response_model=AttemptOut, status_code=status.HTTP_201_CREATED)
def start_attempt(
    payload: AttemptStart,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttemptOut:
    """Create a new attempt. Without an exam the whole bank is used."""
    expire_stale(db)
    exam: Exam | None = None
    if payload.exam_id:
        exam = db.get(Exam, payload.exam_id)
        if exam is None:
            raise HTTPException(status_code=404, detail="Imtihon topilmadi")
        if not exam.is_published and user.role not in (ROLE_ADMIN, ROLE_TEACHER):
            raise HTTPException(status_code=403, detail="Imtihon hali e'lon qilinmagan")

    per_block = exam.questions_per_block if exam else get_int(
        db, "questions_per_block", 20
    )
    time_limit = exam.time_limit_minutes if exam else get_int(
        db, "time_limit_minutes", 30
    )
    pass_percent = exam.pass_percent if exam else get_float(
        db, "default_pass_percent", 60.0
    )
    title = exam.title if exam else "Umumiy test (barcha savollar)"

    try:
        attempt = build_attempt(
            db=db,
            user_id=user.id,
            exam=exam,
            block_number=payload.block_number,
            per_block=per_block,
            time_limit=time_limit,
            pass_percent=pass_percent,
            title=title,
            shuffle_questions=payload.shuffle_questions,
            shuffle_options=payload.shuffle_options,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    attempt.mode = payload.mode if payload.mode in ("exam", "practice") else "exam"
    audit.record(db, user, "attempt.start", "attempt", attempt.id, attempt.title_snapshot)
    db.commit()
    db.refresh(attempt)
    reveal = attempt.mode == "practice"
    return load_attempt_for_user(db, attempt, reveal=reveal)


@router.get("/active", response_model=AttemptOut | None)
def active_attempt(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> AttemptOut | None:
    """Return the unfinished attempt, so the client can resume it."""
    expire_stale(db)
    attempt = db.scalar(
        select(Attempt)
        .where(Attempt.user_id == user.id, Attempt.status == STATUS_IN_PROGRESS)
        .order_by(Attempt.id.desc())
    )
    if attempt is None:
        return None
    db.commit()
    return load_attempt_for_user(
        db, attempt, reveal=(attempt.mode == "practice")
    )
def submit_attempt(
    attempt_id: int,
    payload: AttemptSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttemptOut:
    """Grade the attempt server-side and return the full review."""
    attempt = _get_attempt(db, attempt_id, user)
    if attempt.status == STATUS_SUBMITTED:
        return load_attempt_for_user(db, attempt, reveal=True)
    if remaining_seconds(attempt) <= 0:
        grade_attempt(db, attempt, [], attempt.time_limit_minutes * 60)
        attempt.status = "expired"
    else:
        grade_attempt(
            db,
            attempt,
            [a.model_dump() for a in payload.answers],
            payload.time_spent_seconds,
        )
    audit.record(
        db, user, "attempt.submit", "attempt", attempt.id,
        f"score={attempt.score_percent}",
    )
    db.commit()
    db.refresh(attempt)
    return load_attempt_for_user(db, attempt, reveal=True)


@router.get("/history", response_model=list[AttemptSummary])
def history(
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AttemptSummary]:
    """Past submitted attempts of the current user, newest first."""
    rows = db.scalars(
        select(Attempt)
        .where(Attempt.user_id == user.id, Attempt.status == STATUS_SUBMITTED)
        .order_by(Attempt.id.desc())
        .limit(limit)
    ).all()
    return [AttemptSummary.model_validate(a) for a in rows]


@router.get("/{attempt_id}", response_model=AttemptOut)
def get_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttemptOut:
    attempt = _get_attempt(db, attempt_id, user)
    reveal = attempt.status == STATUS_SUBMITTED or attempt.mode == "practice"
    return load_attempt_for_user(db, attempt, reveal=reveal)


@router.post("/{attempt_id}/abandon", response_model=AttemptOut)
def abandon_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttemptOut:
    """Give up on the current attempt; it is graded with what was answered."""
    attempt = _get_attempt(db, attempt_id, user)
    if attempt.status == STATUS_IN_PROGRESS:
        existing = [
            {"question_id": qid, "selected_index": None}
            for qid in (attempt.question_ids or [])
        ]
        grade_attempt(db, attempt, existing, attempt.time_limit_minutes * 60)
        attempt.status = "abandoned"
        audit.record(db, user, "attempt.abandon", "attempt", attempt.id)
        db.commit()
        db.refresh(attempt)
    return load_attempt_for_user(db, attempt, reveal=True)


@router.get("/{attempt_id}/timer")
def timer(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Remaining seconds for the countdown shown in the client."""
    attempt = _get_attempt(db, attempt_id, user)
    expire_stale(db)
    db.commit()
    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "remaining_seconds": remaining_seconds(attempt),
        "time_limit_minutes": attempt.time_limit_minutes,
    }


@router.post("/{attempt_id}/submit", response_model=AttemptOut)
def submit_attempt(
    attempt_id: int,
    payload: AttemptSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttemptOut:
    """Grade the attempt server-side and return the full review."""
    attempt = _get_attempt(db, attempt_id, user)
    if attempt.status == STATUS_SUBMITTED:
        return load_attempt_for_user(db, attempt, reveal=True)
    if remaining_seconds(attempt) <= 0:
        grade_attempt(db, attempt, [], attempt.time_limit_minutes * 60)
        attempt.status = STATUS_EXPIRED
    else:
        grade_attempt(
            db,
            attempt,
            [a.model_dump() for a in payload.answers],
            payload.time_spent_seconds,
        )
    audit.record(
        db,
        user,
        "attempt.submit",
        "attempt",
        attempt.id,
        f"score={attempt.score_percent}",
    )
    db.commit()
    db.refresh(attempt)
    return load_attempt_for_user(db, attempt, reveal=True)


