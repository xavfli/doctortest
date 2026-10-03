"""Report answer-key coverage: how many bank questions can be graded.

Answers are matched by question text (see import_answers), so the report
answers "which questions still have no key" without writing anything.

Run with:  python tools/answer_coverage.py [answers-file]
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.answers_parser import DEFAULT_PATH, parse  # noqa: E402
from tools.import_answers import DB, plan_updates  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
rows = con.execute(
    "SELECT id, source_id, text, options, answer_index, answer_all, answer_text "
    "FROM questions WHERE is_active=1 ORDER BY source_id, id"
).fetchall()

plan, reasons = plan_updates(parse(path), rows)
matched = {r[0] for r in plan}

keyed = [r for r in rows if r["answer_index"] is not None or r["answer_all"]]
keyed_unverified = [r for r in keyed if r["source_id"] - 1 not in matched]
missing = [r for r in rows if r["answer_index"] is None and not r["answer_all"]
           and r["source_id"] - 1 not in matched]

print(f"answer key file          : {path}")
print(f"bank questions           : {len(rows)}")
print(f"graded (has a key)       : {len(keyed)}")
print(f"ungraded                 : {len(rows) - len(keyed)}")
print()
print(f"key confirmed by this file: {len([r for r in keyed if r['source_id']-1 in matched])}")
print(f"key from an earlier source: {len(keyed_unverified)}")
print(f"still ungraded            : {len(missing)}")

no_opt = [r for r in rows if not json.loads(r["options"] or "[]")]
print(f"\nquestions with no options: {len(no_opt)}"
      f"  (graded: {sum(1 for r in no_opt if r['answer_index'] is not None or r['answer_all'])})")

print("\nskip reasons:")
for reason, nums in sorted(reasons.items(), key=lambda kv: -len(kv[1])):
    print(f"  {reason:<34}: {len(nums)}")

out = ROOT / "build" / "unanswered.json"
out.parent.mkdir(exist_ok=True)
out.write_text(
    json.dumps([r["source_id"] for r in missing], indent=1), encoding="utf-8"
)
print(f"\nungraded source_ids -> {out}")
con.close()
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.answers_parser import DEFAULT_PATH, parse  # noqa: E402
from tools.import_answers import DB, compact, plan_updates, strip_asides  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
rows = con.execute(
    "SELECT id, source_id, text, options, answer_index, answer_all, answer_text "
    "FROM questions WHERE is_active=1 ORDER BY source_id, id"
).fetchall()

plan, reasons = plan_updates(parse(path), rows)
matched = {r[0] for r in plan}

keyed = [r for r in rows if r["answer_index"] is not None or r["answer_all"]]
keyed_unverified = [r for r in keyed if r["source_id"] - 1 not in matched]
missing = [r for r in rows if r not in keyed and r["source_id"] - 1 not in matched]

print(f"answer key file          : {path}")
print(f"bank questions           : {len(rows)}")
print(f"graded (has a key)       : {len(keyed)}")
print(f"ungraded                 : {len(rows) - len(keyed)}")
print()
print(f"key confirmed by this file: {len([r for r in keyed if r['source_id']-1 in matched])}")
print(f"key from an earlier source: {len(keyed_unverified)}")
print(f"still ungraded            : {len(missing)}")

no_opt = [r for r in rows if not json.loads(r["options"] or "[]")]
print(f"\nquestions with no options: {len(no_opt)}"
      f"  (graded: {sum(1 for r in no_opt if r['answer_index'] is not None or r['answer_all'])})")

print("\nskip reasons:")
for reason, nums in sorted(reasons.items(), key=lambda kv: -len(kv[1])):
    print(f"  {reason:<34}: {len(nums)}")

# Mojibake check: Cyrillic text that was decoded through the wrong codepage
# leaves U+2550-style box characters behind.
broken = [r for r in rows if any("\u2550" <= ch <= "\u257f" for ch in r["text"])]
print(f"\nquestions with corrupted text: {len(broken)}")
for r in broken[:5]:
    print(f"  source_id={r['source_id']} {r['text'][:60]!r}")

out = ROOT / "build" / "unanswered.json"
out.parent.mkdir(exist_ok=True)
out.write_text(
    json.dumps([r["source_id"] for r in missing], indent=1), encoding="utf-8"
)
print(f"\nungraded source_ids -> {out}")
con.close()