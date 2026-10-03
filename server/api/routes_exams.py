"""Exam management: create exams, attach questions, publish them."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.api.deps import get_current_user, require_staff
from server.core.database import get_db
from server.models import (
    ROLE_ADMIN,
    ROLE_TEACHER,
    STATUS_SUBMITTED,
    Attempt,
    Exam,
    ExamQuestion,
    Question,
    User,
)
from server.schemas import ExamCreate, ExamOut, ExamUpdate
from server.services import audit

router = APIRouter(prefix="/exams", tags=["exams"])

STAFF_ROLES = (ROLE_ADMIN, ROLE_TEACHER)


def _question_count(db: Session, exam_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(ExamQuestion.id)).where(ExamQuestion.exam_id == exam_id)
        )
        or 0
    )


def _out(db: Session, exam: Exam, detailed: bool = True) -> ExamOut:
    count = _question_count(db, exam.id) if detailed else 0
    attempts = int(
        db.scalar(
            select(func.count(Attempt.id)).where(
                Attempt.exam_id == exam.id, Attempt.status == STATUS_SUBMITTED
            )
        )
        or 0
    )
    avg = db.scalar(
        select(func.avg(Attempt.score_percent)).where(
            Attempt.exam_id == exam.id, Attempt.status == STATUS_SUBMITTED
        )
    )
    return ExamOut(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        questions_per_block=exam.questions_per_block,
        time_limit_minutes=exam.time_limit_minutes,
        pass_percent=exam.pass_percent,
        shuffle_options=exam.shuffle_options,
        shuffle_questions=exam.shuffle_questions,
        is_published=exam.is_published,
        created_at=exam.created_at,
        question_count=count,
        attempt_count=attempts,
        average_score=round(float(avg), 1) if avg is not None else None,
    )


def _sync_questions(db: Session, exam: Exam, question_ids: list[int]) -> None:
    """Replace the exam's question list with the given ids."""
    if not question_ids:
        return
    valid = set(
        db.scalars(select(Question.id).where(Question.id.in_(question_ids))).all()
    )
    missing = [qid for qid in question_ids if qid not in valid]
    if missing:
        raise HTTPException(
            status_code=400, detail=f"Mavjud bo'lmagan savollar: {missing[:10]}"
        )
    for link in db.scalars(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam.id)
    ).all():
        db.delete(link)
    db.flush()
    for position, qid in enumerate(question_ids):
        db.add(ExamQuestion(exam_id=exam.id, question_id=qid, position=position))
    db.flush()


@router.get("", response_model=list[ExamOut])
def list_exams(
    published_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ExamOut]:
    stmt = select(Exam)
    is_staff = user.role in STAFF_ROLES
    if published_only or not is_staff:
        stmt = stmt.where(Exam.is_published.is_(True))
    rows = db.scalars(stmt.order_by(Exam.id)).all()
    return [_out(db, e, detailed=is_staff) for e in rows]


@router.get("/{exam_id}", response_model=ExamOut)
def get_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExamOut:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Imtihon topilmadi")
    if not exam.is_published and user.role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Imtihon hali e'lon qilinmagan")
    return _out(db, exam)


@router.post("", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamCreate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_staff),
) -> ExamOut:
    exam = Exam(
        title=payload.title.strip(),
        description=(payload.description or "").strip() or None,
        questions_per_block=payload.questions_per_block,
        time_limit_minutes=payload.time_limit_minutes,
        pass_percent=payload.pass_percent,
        shuffle_options=payload.shuffle_options,
        shuffle_questions=payload.shuffle_questions,
        is_published=payload.is_published,
        created_by=staff.id,
    )
    db.add(exam)
    db.flush()
    if payload.question_ids:
        _sync_questions(db, exam, payload.question_ids)
    audit.record(db, staff, "exam.create", "exam", exam.id, exam.title)
    db.commit()
    db.refresh(exam)
    return _out(db, exam)


@router.patch("/{exam_id}", response_model=ExamOut)
def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_staff),
) -> ExamOut:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Imtihon topilmadi")
    data = payload.model_dump(exclude_unset=True)
    for field in (
        "title",
        "questions_per_block",
        "time_limit_minutes",
        "pass_percent",
        "shuffle_options",
        "shuffle_questions",
        "is_published",
    ):
        if field in data and data[field] is not None:
            setattr(exam, field, data[field])
    if "description" in data:
        raw_desc = data["description"]
        exam.description = (str(raw_desc).strip() or None) if raw_desc is not None else None
    if data.get("question_ids") is not None:
        _sync_questions(db, exam, data["question_ids"])
    db.flush()
    audit.record(db, staff, "exam.update", "exam", exam.id)
    db.commit()
    db.refresh(exam)
    return _out(db, exam)


@router.delete("/{exam_id}", status_code=200)
def delete_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    staff: User = Depends(require_staff),
) -> dict:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Imtihon topilmadi")
    title = exam.title
    for link in db.scalars(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
    ).all():
        db.delete(link)
    db.delete(exam)
    audit.record(db, staff, "exam.delete", "exam", exam_id, title)
    db.commit()
    return {"deleted": exam_id}

