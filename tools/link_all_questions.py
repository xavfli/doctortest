"""Link every active question into the exam so all 1005 are used.

The exam is worked in blocks of `questions_per_block` (20), and block N is a
slice of the ordered question list, so the number of available blocks is
ceil(active / per_block). Before this script only 455 questions were linked,
which capped the student at 23 blocks and hid the rest of the bank.

Run with:  python tools/link_all_questions.py [--exam 1] [--per-block 20]
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.core.database import SessionLocal, init_db  # noqa: E402
from server.models import Exam, ExamQuestion, Question  # noqa: E402
from sqlalchemy import delete, func, select  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exam", type=int, default=None,
                        help="exam id (default: the only published exam)")
    parser.add_argument("--per-block", type=int, default=20,
                        help="questions per block (default: 20)")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change without writing")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        if args.exam:
            exam = db.get(Exam, args.exam)
        else:
            exam = db.scalar(
                select(Exam).where(Exam.is_published.is_(True)).order_by(Exam.id)
            )
        if exam is None:
            print("E'lon qilingan imtihon topilmadi.")
            return 1

        # Every active question is linked, including the ones that have no
        # answer key yet. grade_attempt() only counts questions with an
        # answer_index in its `gradable` denominator, so an unkeyed question
        # is skipped rather than counted as wrong — students see the full
        # 1005-question bank without being punished for questions nobody can
        # answer correctly yet.
        active = db.scalars(
            select(Question.id)
            .where(Question.is_active.is_(True))
            .order_by(Question.source_id, Question.id)
        ).all()
        keyed = set(
            db.scalars(
                select(Question.id).where(
                    Question.is_active.is_(True),
                    Question.answer_index.isnot(None),
                )
            ).all()
        )

        linked = set(
            db.scalars(
                select(ExamQuestion.question_id).where(ExamQuestion.exam_id == exam.id)
            ).all()
        )
        wanted = list(active)
        added = [qid for qid in wanted if qid not in linked]
        removed = [qid for qid in linked if qid not in set(wanted)]
        blocks = math.ceil(len(wanted) / args.per_block) if wanted else 0

        print(f"imtihon           : #{exam.id} {exam.title}")
        print(f"aktiv savollar    : {len(wanted)}")
        print(f"javobi bor        : {len(keyed)}")
        print(f"javobi yo'q       : {len(wanted) - len(keyed)}  (baho hisobiga kirmaydi)")
        print(f"hozir bog'langan  : {len(linked)}")
        print(f"qo'shiladi        : {len(added)}")
        print(f"olib tashlanadi   : {len(removed)}")
        print(f"bo'laklar         : {blocks} x {args.per_block} savol")
        if blocks * args.per_block - len(wanted):
            print(f"oxirgi bo'lak     : {len(wanted) % args.per_block} ta savol")

        if args.dry_run:
            print("\n(--dry-run: hech narsa yozilmadi)")
            return 0

        if removed:
            db.execute(
                delete(ExamQuestion).where(
                    ExamQuestion.exam_id == exam.id,
                    ExamQuestion.question_id.in_(removed),
                )
            )
        if added:
            start = db.scalar(
                select(func.max(ExamQuestion.position)).where(
                    ExamQuestion.exam_id == exam.id
                )
            ) or 0
            for offset, qid in enumerate(added, start=1):
                db.add(
                    ExamQuestion(
                        exam_id=exam.id, question_id=qid, position=offset
                    )
                )

        exam.questions_per_block = args.per_block
        db.commit()
        print("\nSaqlandi.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())