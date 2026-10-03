"""First-run seeding: default accounts, a starter exam and settings."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.core.config import settings
from server.core.database import session_scope
from server.core.security import hash_password
from server.models import (
    ROLE_ADMIN,
    ROLE_TEACHER,
    Exam,
    ExamQuestion,
    Question,
    User,
)
from server.services.settings import DEFAULTS, set_value


def _ensure_user(
    db: Session, email: str, password: str, full_name: str, role: str
) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        return user
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def seed(db: Session) -> dict:
    """Create default accounts, settings and a starter exam. Idempotent."""
    created: dict[str, int] = {"users": 0, "exams": 0, "settings": 0}

    admin = _ensure_user(
        db,
        settings.DEFAULT_ADMIN_EMAIL,
        settings.DEFAULT_ADMIN_PASSWORD,
        "Administrator",
        ROLE_ADMIN,
    )
    created["users"] += 1
    _ensure_user(
        db,
        settings.DEFAULT_TEACHER_EMAIL,
        settings.DEFAULT_TEACHER_PASSWORD,
        "O‘qituvchi",
        ROLE_TEACHER,
    )
    created["users"] += 1

    for key, value in DEFAULTS.items():
        set_value(db, key, value)
        created["settings"] += 1

    if db.scalar(select(func.count(Question.id))):
        return created

    if not db.scalar(select(func.count(Exam.id))):
        exam = Exam(
            title="Umumiy test — 20 ta savol",
            description=(
                "Oilaviy shifokorlik bo‘limi testi. Har bir urinishda 20 ta savol "
                "tasodifiy tartibda beriladi."
            ),
            questions_per_block=settings.QUESTIONS_PER_BLOCK,
            time_limit_minutes=settings.ATTEMPT_TIME_LIMIT_MINUTES,
            pass_percent=60.0,
            shuffle_options=True,
            shuffle_questions=True,
            is_published=True,
            created_by=admin.id,
        )
        db.add(exam)
        db.flush()
        created["exams"] += 1
        # Attach every active question that has an answer key.
        gradable = db.scalars(
            select(Question.id)
            .where(Question.is_active.is_(True), Question.answer_index.is_not(None))
            .order_by(Question.source_id)
        ).all()
        for position, qid in enumerate(gradable):
            db.add(
                ExamQuestion(exam_id=exam.id, question_id=qid, position=position)
            )
        db.flush()

    return created


def attach_questions_to_starter_exam(db: Session) -> dict:
    """Fill the starter exam with every active, gradable question.

    Called after a bulk import so a fresh database ends up with a usable exam.
    """
    gradable = db.scalars(
        select(Question.id)
        .where(Question.is_active.is_(True), Question.answer_index.is_not(None))
        .order_by(Question.source_id)
    ).all()
    exam = db.scalar(select(Exam).order_by(Exam.id).limit(1))
    if exam is None or not gradable:
        return {"exam_id": exam.id if exam else None, "attached": 0}
    existing = set(
        db.scalars(select(ExamQuestion.question_id).where(ExamQuestion.exam_id == exam.id)).all()
    )
    added = 0
    for qid in gradable:
        if qid in existing:
            continue
        db.add(ExamQuestion(exam_id=exam.id, question_id=qid, position=added))
        added += 1
    db.flush()
    return {"exam_id": exam.id, "attached": added, "total": len(gradable)}


def import_dataset(db: Session, user: User | None = None) -> dict | None:
    """Load build/questions.json into the question table (idempotent)."""
    from server.api.routes_questions import _load_dataset

    try:
        data = _load_dataset(None)
    except HTTPException:
        return None
    existing = {q.source_id: q for q in db.scalars(select(Question)).all()}
    created = updated = 0
    for row in data:
        source_id = int(row.get("id") or 0)
        if not source_id:
            continue
        options = [str(o).strip() for o in (row.get("options") or []) if str(o).strip()]
        answer_index = row.get("answer_index")
        if answer_index is not None:
            answer_index = int(answer_index)
        q = existing.get(source_id)
        if q is None:
            q = Question(source_id=source_id)
            db.add(q)
            created += 1
        else:
            updated += 1
        q.text = str(row.get("question") or "").strip()
        q.options = options
        q.answer_index = answer_index
        q.answer_text = str(row.get("answer") or "").strip() or None
        q.answer_all = bool(row.get("answer_all"))
        q.notes = str(row.get("notes") or "").strip() or None
        q.is_active = True
    db.flush()
    attach_questions_to_starter_exam(db)
    return {"created": created, "updated": updated, "total": len(data)}


def seed_if_empty() -> dict | None:
    """Prepare the database on first run: accounts, settings and questions.

    Idempotent: accounts and settings are created only when missing, and the
    question bank is (re)loaded whenever it is still empty.
    """
    with session_scope() as db:
        created: dict[str, object] = {}
        if not db.scalar(select(func.count(User.id))):
            created.update(seed(db))
        if not db.scalar(select(func.count(Question.id))):
            result = import_dataset(db)
            if result:
                created["questions"] = result
        return created or None
