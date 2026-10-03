"""Exam engine: builds an attempt, grades it, and expires stale runs."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.models import (
    STATUS_EXPIRED,
    STATUS_IN_PROGRESS,
    STATUS_SUBMITTED,
    Answer,
    Attempt,
    Exam,
    ExamQuestion,
    Question,
    utcnow,
)
from server.schemas import AttemptOut, AttemptQuestionOut


def _exam_questions(db: Session, exam: Exam | None) -> list[Question]:
    """Ordered question list for an exam (or the whole bank when exam is None)."""
    if exam is None:
        return list(
            db.scalars(
                select(Question)
                .where(Question.is_active.is_(True))
                .order_by(Question.source_id)
            ).all()
        )
    ids = db.scalars(
        select(ExamQuestion.question_id)
        .where(ExamQuestion.exam_id == exam.id)
        .order_by(ExamQuestion.position)
    ).all()
    if not ids:
        return []
    rows = db.scalars(select(Question).where(Question.id.in_(ids))).all()
    by_id = {q.id: q for q in rows}
    return [by_id[i] for i in ids if i in by_id]


def _elapsed_seconds(attempt: Attempt) -> int:
    end = attempt.finished_at or utcnow()
    start = attempt.started_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return max(0, int((end - start).total_seconds()))


def remaining_seconds(attempt: Attempt) -> int:
    """Seconds left before the attempt expires (never negative)."""
    used = _elapsed_seconds(attempt)
    return max(0, attempt.time_limit_minutes * 60 - used)


def build_attempt(
    db: Session,
    user_id: int,
    exam: Exam | None,
    block_number: int,
    per_block: int,
    time_limit: int,
    pass_percent: float,
    title: str,
    seed: int | None = None,
    shuffle_questions: bool | None = None,
    shuffle_options: bool | None = None,
) -> Attempt:
    """Create an attempt with a fixed, shuffled question and option order.

    Both shuffles are resolved here so the order is decided once and stored on
    the attempt: grading later maps the submitted indices back through the very
    same `option_order`, and the client cannot influence it.

    `shuffle_questions` / `shuffle_options` override the exam defaults when the
    student picks the mode in the start dialog (None = follow the exam).
    """
    pool = [q for q in _exam_questions(db, exam) if q.is_active]
    if not pool:
        raise ValueError("Imtihon uchun savol topilmadi")
    rng = random.Random(seed)

    mix_questions = exam.shuffle_questions if exam else True
    if shuffle_questions is not None:
        mix_questions = shuffle_questions

    # Block N must be the same slice of the bank every time, otherwise a
    # student who retries "block 3" gets a different set of questions and the
    # 1005-question bank is never covered. Shuffling is therefore applied to
    # the *selection*, not to the list it is sliced from: the bank keeps a
    # stable order, and each block draws a per-attempt permutation of its own
    # slice. This still hides the source order from the student.
    ordered = sorted(pool, key=lambda q: q.id)
    start_index = (max(1, block_number) - 1) * per_block
    selected = ordered[start_index : start_index + per_block]
    if not selected:
        # Past the end of the bank: fall back to the first block rather than
        # reshuffling, so block numbers stay meaningful and predictable.
        selected = ordered[:per_block] or ordered
    elif mix_questions:
        rng.shuffle(selected)

    mix_options = exam.shuffle_options if exam else True
    if shuffle_options is not None:
        mix_options = shuffle_options

    option_order: dict[int, list[int]] = {}
    for q in selected:
        count = len(q.options or [])
        order = list(range(count))
        if mix_options and count > 1:
            rng.shuffle(order)
        option_order[q.id] = order

    attempt = Attempt(
        user_id=user_id,
        exam_id=exam.id if exam else None,
        title_snapshot=title,
        block_number=max(1, block_number),
        question_ids=[q.id for q in selected],
        option_order=option_order,
        status=STATUS_IN_PROGRESS,
        time_limit_minutes=time_limit,
        total_questions=len(selected),
    )
    attempt.pass_percent_snapshot = pass_percent  # type: ignore[attr-defined]
    db.add(attempt)
    db.flush()
    return attempt


def grade_attempt(
    db: Session,
    attempt: Attempt,
    answers: list[dict],
    time_spent_seconds: int = 0,
) -> Attempt:
    """Score the attempt server-side and store per-question results.

    `answers` is a list of dicts: {question_id, position, selected_index,
    time_spent_seconds}. The option index sent by the client is mapped back
    through the stored shuffle order, so a shuffled run is graded correctly.
    """
    questions = db.scalars(
        select(Question).where(Question.id.in_(attempt.question_ids or []))
    ).all()
    by_id = {q.id: q for q in questions}
    order_map = attempt.option_order or {}

    for existing in db.scalars(
        select(Answer).where(Answer.attempt_id == attempt.id)
    ).all():
        db.delete(existing)
    db.flush()

    correct = 0
    gradable = 0
    for position, qid in enumerate(attempt.question_ids or []):
        q = by_id.get(qid)
        if q is None:
            continue
        payload = next(
            (a for a in answers if int(a.get("question_id", -1)) == qid), None
        )
        chosen = payload.get("selected_index") if payload else None
        chosen = int(chosen) if chosen is not None else None
        spent = int(payload.get("time_spent_seconds", 0)) if payload else 0

        order = order_map.get(str(qid)) or order_map.get(qid) or list(
            range(len(q.options or []))
        )
        original_index: int | None = None
        if chosen is not None and 0 <= chosen < len(order):
            original_index = int(order[chosen])

        is_correct = False
        if q.answer_index is not None and original_index is not None:
            is_correct = original_index == q.answer_index
        if q.answer_index is not None:
            gradable += 1
            if is_correct:
                correct += 1
        elif q.answer_all:
            # "All of the above" is a real option in the list, so it is graded
            # by locating that option. Falling back to "correct" when the
            # wording cannot be found would let any answer score, so the
            # question is counted as gradable but not answered correctly.
            gradable += 1
            is_correct = False
            if original_index is not None:
                for i, text in enumerate(q.options or []):
                    if "barcha javob" in str(text).lower().replace(" ", ""):
                        is_correct = original_index == i
                        break
            if is_correct:
                correct += 1
            if is_correct:
                correct += 1

        db.add(
            Answer(
                attempt_id=attempt.id,
                question_id=qid,
                position=position,
                selected_index=original_index,
                is_correct=bool(is_correct),
                time_spent_seconds=spent,
            )
        )

    attempt.status = STATUS_SUBMITTED
    attempt.finished_at = utcnow()
    attempt.correct_answers = correct
    attempt.time_spent_seconds = max(0, int(time_spent_seconds))
    attempt.score_percent = round((correct / gradable * 100.0), 1) if gradable else 0.0
    attempt.passed = attempt.score_percent >= (attempt.pass_percent_snapshot or 60.0)
    attempt.total_questions = len(attempt.question_ids or [])
    db.flush()
    return attempt


def expire_stale(db: Session) -> int:
    """Mark attempts whose time limit has passed as expired. Returns count."""
    now = utcnow()
    stale = db.scalars(
        select(Attempt).where(Attempt.status == STATUS_IN_PROGRESS)
    ).all()
    count = 0
    for attempt in stale:
        if remaining_seconds(attempt) <= 0:
            attempt.status = STATUS_EXPIRED
            attempt.finished_at = now
            attempt.time_spent_seconds = attempt.time_limit_minutes * 60
            count += 1
    if count:
        db.flush()
    return count


def load_attempt_for_user(
    db: Session, attempt: Attempt, reveal: bool = False
) -> AttemptOut:
    """Serialise an attempt, including per-question state for the client.

    `reveal=False` hides the correct answer (exam mode); `reveal=True` is used
    after submission or in practice mode.
    """
    questions = db.scalars(
        select(Question).where(Question.id.in_(attempt.question_ids or []))
    ).all()
    by_id = {q.id: q for q in questions}
    answers = {
        a.question_id: a
        for a in db.scalars(
            select(Answer).where(Answer.attempt_id == attempt.id)
        ).all()
    }
    items: list[AttemptQuestionOut] = []
    for position, qid in enumerate(attempt.question_ids or []):
        q = by_id.get(qid)
        if q is None:
            continue
        order = (attempt.option_order or {}).get(str(qid)) or (
            attempt.option_order or {}
        ).get(qid) or list(range(len(q.options or [])))
        options = [q.options[i] for i in order if i < len(q.options or [])]
        answer = answers.get(qid)
        items.append(
            AttemptQuestionOut(
                position=position,
                question_id=q.id,
                text=q.text,
                options=options,
                notes=q.notes if reveal else None,
                # The client sees the SHUFFLED position, so map it back.
                selected_index=(
                    order.index(answer.selected_index)
                    if answer is not None
                    and answer.selected_index is not None
                    and answer.selected_index in order
                    else None
                ),
                answer_index=(
                    order.index(q.answer_index)
                    if reveal
                    and q.answer_index is not None
                    and q.answer_index in order
                    else None
                ),
                answer_text=q.answer_text if reveal else None,
                answer_all=q.answer_all,
                is_correct=(answer.is_correct if reveal and answer else None),
                is_gradable=q.answer_index is not None or q.answer_all,
                topic=q.topic,
            )
        )
    return AttemptOut(
        id=attempt.id,
        exam_id=attempt.exam_id,
        title=attempt.title_snapshot,
        block_number=attempt.block_number,
        status=attempt.status,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        time_limit_minutes=attempt.time_limit_minutes,
        time_spent_seconds=attempt.time_spent_seconds,
        total_questions=attempt.total_questions,
        correct_answers=attempt.correct_answers,
        score_percent=attempt.score_percent,
        passed=attempt.passed,
        mode=attempt.mode or "exam",
        questions=items,
    )


def remaining_seconds_for(attempt: Attempt) -> int:
    """Public helper used by the API to report the countdown."""
    return remaining_seconds(attempt)
