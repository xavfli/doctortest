"""Show why a skipped answer found no matching option.

For each number the importer rejected with "answer matches no option", print the
answer next to the options of the question it was matched to. Most are wording
differences; some are genuinely wrong keys and should stay unwritten.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.answers_parser import parse  # noqa: E402
from tools.import_answers import (  # noqa: E402
    DB, QUESTION_MIN, pick_option, plan_updates, strip_asides,
)

REASON = sys.argv[1] if len(sys.argv) > 1 else "answer matches no option"
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 100

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
rows = con.execute(
    "SELECT id, text, options, answer_index, answer_all FROM questions "
    "WHERE is_active=1 ORDER BY source_id, id"
).fetchall()
con.close()

entries = parse()
by_num = {e["number"]: e for e in entries}
plan, reasons = plan_updates(entries, rows)

# Re-run the match to recover which row each skipped number was aimed at.
from tools.import_answers import norm  # noqa: E402
import difflib  # noqa: E402

db_norm = [norm(r["text"]) for r in rows]
index: dict[str, list[int]] = {}
for i, n in enumerate(db_norm):
    if n:
        index.setdefault(n, []).append(i)

nums = reasons.get(REASON, [])[:LIMIT]
print(f"{REASON}: showing {len(nums)} of {len(reasons.get(REASON, []))}")
print()

for num in nums:
    e = by_num[num]
    key = norm(e["question"])
    if len(index.get(key, ())) == 1:
        row_i = index[key][0]
    else:
        scored = sorted(
            ((difflib.SequenceMatcher(None, key, n).ratio(), i)
             for i, n in enumerate(db_norm)),
            reverse=True,
        )
        row_i = scored[0][1]
    r = rows[row_i]
    opts = json.loads(r["options"] or "[]")
    answer = strip_asides(e["answer"] or "")
    opt, ratio, margin = pick_option(answer, opts)
    print(f"--- answer#{num}  (db id={r['id']}) best ratio={ratio:.2f}")
    print(f"    Q       : {r['text'][:92]}")
    print(f"    answer  : {answer[:92]}")
    for i, o in enumerate(opts):
        mark = "  <- picked" if i == opt else ""
        print(f"      [{i}] {o[:76]}{mark}")
    print()