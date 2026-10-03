"""Match the answer key to the question bank by text, in either script.

The answer file is Latin for 1-362 and Cyrillic for 363-1005, while the bank is
Latin throughout, and the Word file orders questions differently from the answer
file, so position cannot be trusted. Transliterating the Cyrillic into Latin
puts both sides in one script; exact matches are indexed first and the rest are
scored, so weak links can be reviewed before anything is written.

Run with:  python tools/check_alignment.py
"""
from __future__ import annotations

import difflib
import re
import sqlite3
import sys
import unicodedata

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"c:\Users\asad2\OneDrive\Рабочий стол\test bot")

from tools.answers_parser import parse  # noqa: E402
from tools.uzbek_translit import to_latin  # noqa: E402

DB = r"c:\Users\asad2\OneDrive\Рабочий стол\test bot\data\app.db"
THRESHOLD = 0.80

PUNCT = {"–": "-", "—": "-", "−": "-", "‑": "-", "“": '"', "”": '"',
         "«": '"', "»": '"', "…": " ", "’": "'", "ʼ": "'", "ʻ": "'"}


def norm(s: str) -> str:
    """Fold to a comparable form: lower case, apostrophes unified, no punctuation."""
    s = to_latin(unicodedata.normalize("NFKC", s or ""))
    for a, b in PUNCT.items():
        s = s.replace(a, b)
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main() -> int:
    entries = parse()
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT id, text, options FROM questions WHERE is_active=1 "
        "ORDER BY source_id, id"
    ).fetchall()
    con.close()

    db_norm = [(qid, norm(text)) for qid, text, _ in rows]

    index: dict[str, list[int]] = {}
    for i, (_, n) in enumerate(db_norm):
        if n:
            index.setdefault(n, []).append(i)

    resolved: dict[int, tuple[int, float, str]] = {}
    unmatched: list[int] = []
    for e in entries:
        key = norm(e["question"])
        if not key:
            unmatched.append(e["number"])
            continue
        if len(index.get(key, ())) == 1:
            resolved[e["number"]] = (index[key][0], 1.0, "exact")
            continue
        best_i, best_r = -1, 0.0
        for i, (_, n) in enumerate(db_norm):
            r = difflib.SequenceMatcher(None, key, n).ratio()
            if r > best_r:
                best_i, best_r = i, r
        if best_r >= THRESHOLD:
            resolved[e["number"]] = (best_i, best_r, "fuzzy")
        else:
            unmatched.append(e["number"])

    n_exact = sum(1 for v in resolved.values() if v[2] == "exact")
    n_fuzzy = sum(1 for v in resolved.values() if v[2] == "fuzzy")

    print(f"answer keys         : {len(entries)}")
    print(f"db questions        : {len(rows)}")
    print(f"resolved exact      : {n_exact}")
    print(f"resolved fuzzy >={THRESHOLD}: {n_fuzzy}")
    print(f"unresolved          : {len(unmatched)}")
    if unmatched:
        print(f"  numbers: {unmatched[:20]}")

    amb = {k: v for k, v in index.items() if len(v) > 1}
    print(f"ambiguous db texts  : {len(amb)}")

    # Two answer keys landing on one question would silently overwrite it.
    seen: dict[int, list[int]] = {}
    for num, (row, _, _) in resolved.items():
        seen.setdefault(row, []).append(num)
    collided = {r: ns for r, ns in seen.items() if len(ns) > 1}
    print(f"rows claimed twice  : {len(collided)}")
    for row, nums in list(collided.items())[:5]:
        print(f"    row {row} <- answers {sorted(nums)}")

    ratios = sorted(v[1] for v in resolved.values())
    if ratios:
        n = len(ratios)
        print()
        print("similarity of resolved matches:")
        print(f"  min {ratios[0]:.2f}  p05 {ratios[int(.05*n)]:.2f}  "
              f"median {ratios[n//2]:.2f}  max {ratios[-1]:.2f}")

    by_num = {e["number"]: e for e in entries}
    pos_ok = sum(
        1 for i in range(min(len(rows), len(entries)))
        if norm(by_num.get(i + 1, {}).get("question", "")) == db_norm[i][1]
    )
    print(f"positional agreement (row N == entry N): {pos_ok}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())