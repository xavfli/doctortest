"""Question bank endpoints: browse, edit, and import from the built dataset."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from server.api.deps import get_current_user, require_staff
from server.core.config import settings
from server.core.database import get_db
from server.models import ROLE_TEACHER, Question, User
from server.schemas import (
    QuestionCreate,
    QuestionImportResult,
    QuestionOut,
    QuestionPage,
    QuestionUpdate,
)
from server.services import audit

router = APIRouter(prefix="/questions", tags=["questions"])


def _out(q: Question) -> QuestionOut:
    return QuestionOut(
        id=q.id,
        source_id=q.source_id,
        text=q.text,
        options=list(q.options or []),
        answer_index=q.answer_index,
        answer_text=q.answer_text,
        answer_all=q.answer_all,
        notes=q.notes,
        topic=q.topic,
        difficulty=q.difficulty,
        is_active=q.is_active,
    )


@router.get("", response_model=QuestionPage)
def list_questions(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=200),
    search: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    gradable: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> QuestionPage:
    stmt = select(Question)
    count_stmt = select(func.count(Question.id))
    if search:
        like = f"%{search.lower()}%"
        cond = or_(
            func.lower(Question.text).like(like),
            func.lower(func.coalesce(Question.notes, "")).like(like),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    if topic:
        stmt = stmt.where(Question.topic == topic)
        count_stmt = count_stmt.where(Question.topic == topic)
    if difficulty:
        stmt = stmt.where(Question.difficulty == difficulty)
        count_stmt = count_stmt.where(Question.difficulty == difficulty)
    if is_active is not None:
        stmt = stmt.where(Question.is_active == is_active)
        count_stmt = count_stmt.where(Question.is_active == is_active)
    if gradable is True:
        stmt = stmt.where(Question.answer_index.is_not(None))
        count_stmt = count_stmt.where(Question.answer_index.is_not(None))
    total = int(db.scalar(count_stmt) or 0)
    rows = db.scalars(
        stmt.order_by(Question.source_id).offset((page - 1) * per_page).limit(per_page)
    ).all()
    return QuestionPage(
        items=[_out(q) for q in rows],
        total=total,
        page=page,
        pages=max(1, (total + per_page - 1) // per_page),
        per_page=per_page,
    )


@router.get("/topics", response_model=list[str])
def list_topics(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[str]:
    rows = db.execute(
        select(Question.topic).distinct().order_by(Question.topic)
    ).scalars().all()
    return list(rows)


@router.get("/{question_id}", response_model=QuestionOut)
def get_question(
    question_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> QuestionOut:
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Savol topilmadi")
    return _out(q)

@router.post("", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
def create_question(
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_staff),
) -> QuestionOut:
    options = [o.strip() for o in payload.options if o and o.strip()]
    if len(options) < 2:
        raise HTTPException(status_code=400, detail="Kamida 2 ta variant kerak")
    if payload.answer_index is not None and not 0 <= payload.answer_index < len(options):
        raise HTTPException(status_code=400, detail="To‘g‘ri javob tartibi noto‘g‘ri")
    source_id = payload.source_id
    if source_id is None:
        max_id = db.scalar(select(func.max(Question.source_id))) or 0
        source_id = int(max_id) + 1
    elif db.scalar(select(Question).where(Question.source_id == source_id)):
        raise HTTPException(status_code=409, detail="Bunday manba raqami mavjud")
    q = Question(
        source_id=source_id,
        text=payload.text.strip(),
        options=options,
        answer_index=payload.answer_index,
        answer_text=(payload.answer_text or "").strip() or None,
        answer_all=payload.answer_all,
        notes=(payload.notes or "").strip() or None,
        topic=(payload.topic or "Umumiy").strip() or "Umumiy",
        difficulty=payload.difficulty,
        is_active=payload.is_active,
    )
    db.add(q)
    db.flush()
    audit.record(db, staff, "question.create", "question", q.id, f"src={q.source_id}")
    db.commit()
    db.refresh(q)
    return _out(q)


@router.patch("/{question_id}", response_model=QuestionOut)
def update_question(
    question_id: int,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_staff),
) -> QuestionOut:
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Savol topilmadi")
    data = payload.model_dump(exclude_unset=True)
    if data.get("text"):
        q.text = str(data["text"]).strip()
    if data.get("options") is not None:
        options = [o.strip() for o in data["options"] if o and o.strip()]
        if len(options) < 2:
            raise HTTPException(status_code=400, detail="Kamida 2 ta variant kerak")
        q.options = options
    if "answer_index" in data:
        idx = data["answer_index"]
        if idx is not None and not 0 <= idx < len(q.options or []):
            raise HTTPException(status_code=400, detail="To‘g‘ri javob tartibi noto‘g‘ri")
        q.answer_index = idx
    if "answer_text" in data and data["answer_text"] is not None:
        q.answer_text = str(data["answer_text"]).strip() or None
    if "notes" in data and data["notes"] is not None:
        q.notes = str(data["notes"]).strip() or None
    if data.get("topic"):
        q.topic = str(data["topic"]).strip() or "Umumiy"
    if data.get("difficulty"):
        q.difficulty = str(data["difficulty"]).strip()
    if data.get("answer_all") is not None:
        q.answer_all = bool(data["answer_all"])
    if data.get("is_active") is not None:
        q.is_active = bool(data["is_active"])
    db.flush()
    audit.record(db, staff, "question.update", "question", q.id)
    db.commit()
    db.refresh(q)
    return _out(q)


@router.delete("/{question_id}", status_code=200)
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    staff: User = Depends(require_staff),
) -> dict:
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Savol topilmadi")
    source_id = q.source_id
    db.delete(q)
    audit.record(db, staff, "question.delete", "question", question_id, f"src={source_id}")
    db.commit()
    return {"deleted": question_id, "source_id": source_id}


def _load_dataset(path: str | None) -> list[dict]:
    """Read the dataset produced by tools/build_dataset.py."""
    candidates = []
    if path:
        candidates.append(Path(path))
    candidates.append(settings.BUILD_DIR / "questions.json")
    candidates.append(settings.WEB_DIR / "questions.js")
    for candidate in candidates:
        if not candidate.exists():
            continue
        text = candidate.read_text(encoding="utf-8")
        if candidate.suffix == ".js":
            start, end = text.index("["), text.rindex("]")
            text = text[start : end + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=f"JSON parse xatosi: {exc}")
    raise HTTPException(status_code=400, detail="Dataset fayli topilmadi")


@router.post("/import", response_model=QuestionImportResult)
def import_questions(
    path: str | None = None,
    activate_all: bool = True,
    db: Session = Depends(get_db),
    staff: User = Depends(require_staff),
) -> QuestionImportResult:
    """Load questions.json into the database (upsert by source_id)."""
    data = _load_dataset(path)
    created = updated = skipped = graded = ungraded = 0
    existing = {q.source_id: q for q in db.scalars(select(Question)).all()}
    for row in data:
        source_id = int(row.get("id") or 0)
        if not source_id:
            skipped += 1
            continue
        options = [str(o).strip() for o in (row.get("options") or []) if str(o).strip()]
        answer_index = row.get("answer_index")
        if answer_index is not None:
            answer_index = int(answer_index)
        if answer_index is None and not row.get("answer_all"):
            ungraded += 1
        else:
            graded += 1
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
        if activate_all:
            q.is_active = True
    audit.record(
        db, staff, "question.import", "question", None,
        f"created={created} updated={updated} skipped={skipped}",
    )
    # A fresh database has no exam questions yet: attach them so the seeded
    # starter exam is immediately usable.
    from server.services.seed import attach_questions_to_starter_exam

    attach_questions_to_starter_exam(db)
    db.commit()
    return QuestionImportResult(
        created=created,
        updated=updated,
        skipped=skipped,
        total_in_file=len(data),
        graded=graded,
        ungraded=ungraded,
    )

