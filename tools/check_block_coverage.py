"""Check the exam links every active question, so the block count is honest.

The student-facing block count is not stored anywhere: it is
`ceil(linked questions / questions_per_block)`. A seeder that links only the
questions that have an answer key therefore silently hides most of the bank —
1005 questions became 23 blocks instead of 51, and nothing in the UI said why.
A fresh deploy reproduces it, so this checks the seeding path directly against a
throwaway database rather than only the current one.

Run with:  python tools/check_block_coverage.py
"""
from __future__ import annotations

import math
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PER_BLOCK = 20
EXPECTED_QUESTIONS = 1005
EXPECTED_BLOCKS = 51

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f" - {detail}" if detail else ""))
    if not ok:
        failures.append(label)


def seed_fresh_database() -> tuple[int, int]:
    """Seed a brand-new database in a temp dir; return (linked, questions)."""
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "check.db")
    saved = {
        key: os.environ.get(key)
        for key in ("DB_PATH", "DB_URL", "DATABASE_URL", "ENVIRONMENT")
    }
    os.environ["DB_PATH"] = db
    os.environ["DB_URL"] = "sqlite:///" + db.replace("\\", "/")
    os.environ["ENVIRONMENT"] = "production"
    os.environ.setdefault("SECRET_KEY", "x" * 48)

    # The config and the engine are built at import time, so they have to be
    # imported only after the variables above are in place.
    for module in [m for m in list(sys.modules) if m.startswith("server.")]:
        del sys.modules[module]
    from server.core.database import init_db, session_scope  # noqa: E402
    from server.models import ExamQuestion, Question  # noqa: E402
    from server.services.seed import seed_if_empty  # noqa: E402
    from sqlalchemy import func, select  # noqa: E402

    init_db()
    seed_if_empty()
    with session_scope() as db_session:
        linked = int(db_session.scalar(select(func.count(ExamQuestion.id))) or 0)
        questions = int(db_session.scalar(select(func.count(Question.id))) or 0)
        positions = list(
            db_session.scalars(
                select(ExamQuestion.position).order_by(ExamQuestion.position)
            ).all()
        )
    shutil.rmtree(tmp, ignore_errors=True)

    # Contiguous positions: block N slices this list, so a gap or a duplicate
    # would shift every block after it.
    if positions != list(range(len(positions))):
        check("positions are contiguous from 0", False, f"got {positions[:6]}...")
    else:
        check("positions are contiguous from 0", True)

    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    return linked, questions


linked, questions = seed_fresh_database()
blocks = math.ceil(linked / PER_BLOCK) if linked else 0

check("fresh database loads the whole bank", questions == EXPECTED_QUESTIONS,
      f"got {questions}")
check("fresh database links every active question", linked == questions,
      f"linked {linked} of {questions}")
check("fresh database exposes all blocks", blocks == EXPECTED_BLOCKS,
      f"got {blocks} blocks, expected {EXPECTED_BLOCKS}")

print()
if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
    raise SystemExit(1)
print(f"A fresh deploy shows {blocks} blocks of {PER_BLOCK} ({linked} questions).")