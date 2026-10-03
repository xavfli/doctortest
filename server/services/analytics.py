"""Analytics: aggregate scores, topic performance and question difficulty."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from server.models import (
    Answer,
    Attempt,
    Exam,
    Question,
    STATUS_SUBMITTED,
    User,
    utcnow,
)
from server.schemas import (
    AdminStats,
    AttemptSummary,
    DifficultyStat,
    QuestionStat,
    TopicStat,
    UserStat,
)

SCORE_BUCKETS = [
    (0, 20, "0–20"),
    (20, 40, "20–40"),
    (40, 60, "40–60"),
    (60, 80, "60–80"),
    (80, 101, "80–100"),
]


def _pct(part: int, whole: int) -> float:
    return round(part / whole * 100.0, 1) if whole else 0.0


def collect(db: Session) -> AdminStats:
    """Build the full dashboard payload in one pass."""
    users_total = int(db.scalar(select(func.count(User.id))) or 0)
    users_active = int(
        db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0
    )
    role_counts = dict(
        db.execute(select(User.role, func.count(User.id)).group_by(User.role)).all()
    )
    questions_total = int(db.scalar(select(func.count(Question.id))) or 0)
    questions_gradable = int(
        db.scalar(
            select(func.count(Question.id)).where(Question.answer_index.is_not(None))
        )
        or 0
    )
    questions_inactive = int(
        db.scalar(
            select(func.count(Question.id)).where(Question.is_active.is_(False))
        )
        or 0
    )
    exams_total = int(db.scalar(select(func.count(Exam.id))) or 0)
    exams_published = int(
        db.scalar(
            select(func.count(Exam.id)).where(Exam.is_published.is_(True))
        )
        or 0
    )
    attempts_total = int(db.scalar(select(func.count(Attempt.id))) or 0)
    submitted = db.scalar(
        select(func.count(Attempt.id)).where(Attempt.status == STATUS_SUBMITTED)
    )
    attempts_submitted = int(submitted or 0)
    avg_score = db.scalar(
        select(func.avg(Attempt.score_percent)).where(Attempt.status == STATUS_SUBMITTED)
    )
    passed = int(
        db.scalar(
            select(func.count(Attempt.id)).where(
                Attempt.status == STATUS_SUBMITTED, Attempt.passed.is_(True)
            )
        )
        or 0
    )
    today = utcnow().date()
    attempts_today = int(
        db.scalar(
            select(func.count(Attempt.id)).where(
                func.date(Attempt.started_at) == today.isoformat()
            )
        )
        or 0
    )
    week_ago = utcnow() - timedelta(days=7)
    active_users_7d = int(
        db.scalar(
            select(func.count(func.distinct(Attempt.user_id))).where(
                Attempt.started_at >= week_ago
            )
        )
        or 0
    )
    return AdminStats(
        users_total=users_total,
        users_active=users_active,
        students=int(role_counts.get("student", 0)),
        teachers=int(role_counts.get("teacher", 0)),
        admins=int(role_counts.get("admin", 0)),
        questions_total=questions_total,
        questions_gradable=questions_gradable,
        questions_inactive=questions_inactive,
        exams_total=exams_total,
        exams_published=exams_published,
        attempts_total=attempts_total,
        attempts_submitted=attempts_submitted,
        average_score=round(float(avg_score), 1) if avg_score is not None else 0.0,
        pass_rate=_pct(passed, attempts_submitted),
        attempts_today=attempts_today,
        active_users_7d=active_users_7d,
    )


def score_distribution(db: Session) -> list[dict]:
    """Histogram of submitted scores."""
    rows = db.scalars(
        select(Attempt.score_percent).where(Attempt.status == STATUS_SUBMITTED)
    ).all()
    buckets = [{"label": label, "count": 0} for _, _, label in SCORE_BUCKETS]
    for score in rows:
        for i, (low, high, _label) in enumerate(SCORE_BUCKETS):
            if low <= score < high:
                buckets[i]["count"] += 1
                break
    return buckets


def topic_stats(db: Session) -> list[TopicStat]:
    """Correct-answer rate per topic, based on stored answers."""
    rows = db.execute(
        select(Question.topic, Answer.is_correct, func.count(Answer.id))
        .join(Answer, Answer.question_id == Question.id)
        .join(Attempt, Attempt.id == Answer.attempt_id)
        .where(Attempt.status == STATUS_SUBMITTED, Question.answer_index.is_not(None))
        .group_by(Question.topic, Answer.is_correct)
    ).all()
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for topic, is_correct, count in rows:
        totals[topic][1] += count
        if is_correct:
            totals[topic][0] += count
    out = [
        TopicStat(
            topic=topic,
            total=total,
            correct=correct,
            percent=_pct(correct, total),
        )
        for topic, (correct, total) in totals.items()
    ]
    return sorted(out, key=lambda t: t.percent)


def difficulty_stats(db: Session) -> list[DifficultyStat]:
    """Correct-answer rate per difficulty label."""
    rows = db.execute(
        select(Question.difficulty, Answer.is_correct, func.count(Answer.id))
        .join(Answer, Answer.question_id == Question.id)
        .join(Attempt, Attempt.id == Answer.attempt_id)
        .where(Attempt.status == STATUS_SUBMITTED, Question.answer_index.is_not(None))
        .group_by(Question.difficulty, Answer.is_correct)
    ).all()
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for difficulty, is_correct, count in rows:
        totals[difficulty][1] += count
        if is_correct:
            totals[difficulty][0] += count
    return [
        DifficultyStat(
            difficulty=difficulty,
            total=total,
            correct=correct,
            percent=_pct(correct, total),
        )
        for difficulty, (correct, total) in sorted(totals.items())
    ]


def hardest_questions(db: Session, limit: int = 10) -> list[QuestionStat]:
    """Questions answered most often and most often wrong."""
    correct_expr = cast(Answer.is_correct, Integer)
    rows = db.execute(
        select(
            Question.id,
            Question.source_id,
            Question.text,
            func.count(Answer.id),
            func.sum(correct_expr),
        )
        .join(Answer, Answer.question_id == Question.id)
        .join(Attempt, Attempt.id == Answer.attempt_id)
        .where(Attempt.status == STATUS_SUBMITTED, Question.answer_index.is_not(None))
        .group_by(Question.id)
        .having(func.count(Answer.id) > 0)
        .order_by((func.sum(correct_expr) / func.count(Answer.id)).asc())
        .limit(limit)
    ).all()
    return [
        QuestionStat(
            question_id=qid,
            source_id=source_id,
            text=text,
            attempts=attempts,
            correct=int(correct or 0),
            percent=_pct(int(correct or 0), attempts),
        )
        for qid, source_id, text, attempts, correct in rows
    ]


def top_users(db: Session, limit: int = 10) -> list[UserStat]:
    """Leaderboard by average score (minimum one submitted attempt)."""
    rows = db.execute(
        select(
            User.id,
            User.full_name,
            User.email,
            func.count(Attempt.id),
            func.avg(Attempt.score_percent),
            func.max(Attempt.score_percent),
        )
        .join(Attempt, Attempt.user_id == User.id)
        .where(Attempt.status == STATUS_SUBMITTED)
        .group_by(User.id)
        .having(func.count(Attempt.id) > 0)
        .order_by(func.avg(Attempt.score_percent).desc())
        .limit(limit)
    ).all()
    return [
        UserStat(
            user_id=uid,
            full_name=full_name,
            email=email,
            attempts=int(attempts),
            average_score=round(float(avg), 1),
            best_score=round(float(best), 1),
        )
        for uid, full_name, email, attempts, avg, best in rows
    ]


def recent_attempts(db: Session, limit: int = 20) -> list[AttemptSummary]:
    """Latest submitted attempts across all users."""
    rows = db.scalars(
        select(Attempt)
        .where(Attempt.status == STATUS_SUBMITTED)
        .order_by(Attempt.id.desc())
        .limit(limit)
    ).all()
    return [AttemptSummary.model_validate(a) for a in rows]


def daily_activity(db: Session, days: int = 14) -> list[dict]:
    """Attempts per day for the last N days, oldest first."""
    start = (utcnow() - timedelta(days=days - 1)).date()
    rows = db.execute(
        select(func.date(Attempt.started_at), func.count(Attempt.id))
        .group_by(func.date(Attempt.started_at))
    ).all()
    counts = {str(d): int(c) for d, c in rows if d}
    out = []
    for offset in range(days):
        day = str(start + timedelta(days=offset))
        out.append({"date": day, "count": counts.get(day, 0)})
    return out


def full_stats(db: Session) -> AdminStats:
    """Dashboard payload with every breakdown filled in."""
    stats = collect(db)
    stats.score_distribution = score_distribution(db)
    stats.topic_stats = topic_stats(db)
    stats.difficulty_stats = difficulty_stats(db)
    stats.hardest_questions = hardest_questions(db)
    stats.top_users = top_users(db)
    stats.recent_attempts = recent_attempts(db)
    stats.daily_activity = daily_activity(db)
    return stats

