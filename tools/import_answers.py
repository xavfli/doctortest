"""Import answer keys from the answer file into the question bank.

Only answer keys are ever written: question text, options, block/exam membership
and attempt history are left exactly as they are. Two conditions must both hold
before a key is written, because a wrong answer is worse than a missing one:

  1. the answer file's question text must identify one bank question — an exact
     normalised match, an exact match ignoring stray spaces, or a fuzzy match
     that also beats every other candidate;
  2. the answer text must pick out exactly one of that question's options.

Anything failing either test is reported and left untouched. Run with --dry-run
first; it prints the plan without writing.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.answers_parser import DEFAULT_PATH, parse  # noqa: E402
from tools.uzbek_translit import to_latin  # noqa: E402

DB = ROOT / "data" / "app.db"

QUESTION_MIN = 0.80      # fuzzy floor for matching a question
QUESTION_MARGIN = 0.03   # how far the best must beat the runner-up
OPTION_MIN = 0.80        # fuzzy floor for picking an option
OPTION_MARGIN = 0.05

PUNCT = {"–": "-", "—": "-", "−": "-", "‑": "-", "“": '"', "”": '"',
         "«": '"', "»": '"', "…": " ", "’": "'", "ʼ": "'", "ʻ": "'"}

# Explanatory asides open with "*(" and are not always closed the same way: the
# answer file has "splenit *(taloq chap tomonda)", "...*", and "...).*" (the
# closing asterisk after a full stop). The opening asterisk is what distinguishes
# an aside from a real parenthesis such as "TTG (tireotrop)", so only a "(...)"
# preceded by "*" is stripped, together with any stray dots and asterisks that
# trail it — otherwise a leftover ".*" is compared against the options as if it
# were part of the answer.
ASIDE = re.compile(r"\s*\*\s*\([^)]*\)[\s.*]*")

# The Cyrillic half appends the doctor's commentary after the key, in two shapes:
# a bare "Izoh: ..." paragraph and a trailing "Yoki muqobil ravishda: ...".
# Either way the key itself is everything before it.
TRAILER = re.compile(
    r"\s*(?:Izoh|Izohlari|izoh|Yoki\s+muqobil(?:\s+ravishda)?)\s*:.*$",
    re.IGNORECASE | re.DOTALL,
)


def norm(s: str) -> str:
    s = to_latin(unicodedata.normalize("NFKC", s or ""))
    for a, b in PUNCT.items():
        s = s.replace(a, b)
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def compact(s: str) -> str:
    """`norm` without spaces.

    The bank was extracted from a PDF whose columns sometimes split a word
    ("homilado rlar", "yirin g"), so the same question can differ from the
    answer file only by stray spaces. Removing spaces makes those compare equal
    without weakening the test in any other way.
    """
    return norm(s).replace(" ", "")


def strip_asides(answer: str) -> str:
    """Remove `*(...)*` explanations and any trailing commentary."""
    prev, text = None, answer or ""
    while text != prev:
        prev = text
        text = ASIDE.sub(" ", text)
    text = TRAILER.sub("", text)
    return re.sub(r"\s+", " ", text).strip(" .;,")


def pick_option(answer: str, options: list[str]) -> tuple[int, float, float]:
    """Return (index, best_ratio, margin) for the closest option.

    Compared with spaces removed, so the bank's split words ("homilado rlar")
    match the answer file's clean spelling.
    """
    a = compact(answer)
    if not a or not options:
        return -1, 0.0, 0.0
    scored = sorted(
        ((difflib.SequenceMatcher(None, a, compact(o)).ratio(), i)
         for i, o in enumerate(options)),
        reverse=True,
    )
    best_r, best_i = scored[0]
    margin = best_r - (scored[1][0] if len(scored) > 1 else 0.0)
    return best_i, best_r, margin


def pick_by_containment(answer: str, options: list[str]) -> int:
    """Match an abbreviated answer such as "o'pka" to "o'pka shishi".

    Only one option may contain the answer (or be contained by it), so an
    abbreviation that fits several choices is rejected rather than guessed.
    Returns -1 when nothing, or more than one thing, fits.
    """
    a = compact(answer)
    if len(a) < 4:
        return -1
    hits = [
        i for i, o in enumerate(options)
        if (a in compact(o) or compact(o) in a) and compact(o)
    ]
    return hits[0] if len(hits) == 1 else -1


def plan_updates(entries: list[dict], rows: list[sqlite3.Row]) -> tuple:
    """Work out which keys are safe to write.

    Returns (plan, reasons). Each plan entry is (row, option index, answer text,
    answer-file number); `reasons` maps a skip reason to the numbers skipped.
    """
    db_norm = [compact(r["text"]) for r in rows]
    index: dict[str, list[int]] = {}
    for i, n in enumerate(db_norm):
        if n:
            index.setdefault(n, []).append(i)

    plan: list[tuple[int, int, str, int]] = []
    reasons: dict[str, list[int]] = {}
    claimed: dict[int, int] = {}

    def reject(reason: str, num: int) -> None:
        reasons.setdefault(reason, []).append(num)

    for e in entries:
        key = compact(e["question"])
        if not key:
            reject("empty question text", e["number"])
            continue

        if len(index.get(key, ())) == 1:
            row = index[key][0]
        else:
            scored = sorted(
                ((difflib.SequenceMatcher(None, key, n).ratio(), i)
                 for i, n in enumerate(db_norm)),
                reverse=True,
            )
            best_r, row = scored[0]
            margin = best_r - (scored[1][0] if len(scored) > 1 else 0.0)
            if best_r < QUESTION_MIN:
                reject("question not in bank", e["number"])
                continue
            if margin < QUESTION_MARGIN:
                reject("question ambiguous", e["number"])
                continue

        if row in claimed:
            reject("question already claimed", e["number"])
            continue

        answer = strip_asides(e["answer"] or "")
        # Asides often carry the doctor's real correction ("savol chala qolgan,
        # javob ko'pincha ... bo'ladi"), so an entry that had one is not a
        # candidate for the loose containment fallback.
        had_aside = answer != (e["answer"] or "").strip()
        options = json.loads(rows[row]["options"] or "[]")
        if not answer:
            reject("no answer text", e["number"])
            continue
        if not options:
            reject("question has no options", e["number"])
            continue

        claimed[row] = e["number"]

        # "barcha javoblar to'g'ri" needs no special case: the question lists
        # it as a literal option, so ordinary option matching already picks it
        # and keeps the key in the same shape as every other question.
        opt, ratio, margin = pick_option(answer, options)
        if opt < 0 or ratio < OPTION_MIN:
            fallback = -1 if had_aside else pick_by_containment(answer, options)
            if fallback >= 0:
                plan.append((row, fallback, answer, e["number"]))
                continue
            claimed.pop(row)
            reject("answer matches no option", e["number"])
            continue
        if margin < OPTION_MARGIN:
            fallback = -1 if had_aside else pick_by_containment(answer, options)
            if fallback >= 0:
                plan.append((row, fallback, answer, e["number"]))
                continue
            claimed.pop(row)
            reject("answer ambiguous between options", e["number"])
            continue
        plan.append((row, opt, answer, e["number"]))

    return plan, reasons


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change without writing")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after N changed keys (0 = all)")
    ap.add_argument("--report", default="",
                    help="write the skipped entry numbers to this JSON file")
    ap.add_argument("--answers", default=DEFAULT_PATH,
                    help=f"answer key file (default: {DEFAULT_PATH})")
    args = ap.parse_args()

    entries = parse(args.answers)
    print(f"answer key file       : {args.answers}")
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, text, options, answer_index, answer_all FROM questions "
        "WHERE is_active=1 ORDER BY source_id, id"
    ).fetchall()

    plan, reasons = plan_updates(entries, rows)

    changes = [
        p for p in plan
        if rows[p[0]]["answer_index"] != p[1]
        or bool(rows[p[0]]["answer_all"])
    ]
    unchanged = len(plan) - len(changes)

    print(f"answer keys read      : {len(entries)}")
    print(f"accepted              : {len(plan)}")
    print(f"  would change a key  : {len(changes)}")
    print(f"  already correct     : {unchanged}")
    print()
    for reason, nums in sorted(reasons.items(), key=lambda kv: -len(kv[1])):
        print(f"skipped {reason:<34}: {len(nums)}")

    if args.report:
        Path(args.report).write_text(
            json.dumps(reasons, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nskip report -> {args.report}")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        con.close()
        return 0

    if args.limit:
        changes = changes[:args.limit]

    for row, opt, answer, _num in changes:
        con.execute(
            "UPDATE questions SET answer_index=?, answer_all=0, "
            "answer_text=? WHERE id=?",
            (opt, answer, rows[row]["id"]),
        )
    con.commit()

    keyed = con.execute(
        "SELECT COUNT(*) FROM questions WHERE answer_index IS NOT NULL OR answer_all=1"
    ).fetchone()[0]
    con.close()
    print(f"\nwritten : {len(changes)}")
    print(f"bank now has {keyed} gradable questions of {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
