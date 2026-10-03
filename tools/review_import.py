"""Print the details behind an import run so every decision can be eyeballed.

Shows the keys that would change (the risky ones) and samples of each skip
reason, with the question, the file's answer and the options side by side.
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
from tools.import_answers import DB, plan_updates  # noqa: E402

WANT_CHANGES = 26
PER_SKIP = 4

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


def show(label: str, row_i: int, num: int, new_opt: int) -> None:
    r = rows[row_i]
    opts = json.loads(r["options"] or "[]")
    e = by_num.get(num, {})
    cur = "answer_all" if r["answer_all"] else str(r["answer_index"])
    print(f"--- {label} answer#{num}  (db id={r['id']}) -> opt {new_opt}")
    print(f"    Q    : {r['text'][:96]}")
    print(f"    file : {(e.get('answer') or '')[:96]}")
    print(f"    db   : {cur}")
    for i, o in enumerate(opts):
        mark = "  <- db" if i == r["answer_index"] else ""
        print(f"      [{i}] {o[:78]}{mark}")
    print()


changes = [p for p in plan
           if rows[p[0]]["answer_index"] != p[1]
           or bool(rows[p[0]]["answer_all"])]

print(f"KEYS THAT WOULD CHANGE: {len(changes)}")
print()
for row_i, opt, _answer, num in changes[:WANT_CHANGES]:
    show("CHANGE", row_i, num, opt)

print("=" * 72)
print("SKIP SAMPLES")
for reason, nums in sorted(reasons.items(), key=lambda kv: -len(kv[1])):
    if reason == "question not in bank":
        continue
    print(f"\n### {reason}  ({len(nums)} total)")
    for num in nums[:PER_SKIP]:
        e = by_num[num]
        print(f"--- answer#{num}")
        print(f"    Q    : {e['question'][:96]}")
        print(f"    file : {(e['answer'] or '')[:96]}")
        from tools.import_answers import norm
        import difflib
        key = norm(e["question"])
        scored = sorted(
            ((difflib.SequenceMatcher(None, key, norm(r["text"])).ratio(), i)
             for i, r in enumerate(rows)),
            reverse=True,
        )
        best_r, row_i = scored[0]
        opts = json.loads(rows[row_i]["options"] or "[]")
        print(f"    nearest db q (r={best_r:.2f}): {rows[row_i]['text'][:88]}")
        for i, o in enumerate(opts):
            print(f"      [{i}] {o[:78]}")
        print()