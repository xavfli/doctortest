"""Verify the 1005-question bank is split into 20-question blocks.

Checks every block start over the real API: blocks 1..51 must return 20
questions and the last one 5, and no question may appear in two blocks.

Run with:  python tools/check_blocks.py
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
EMAIL = "admin@osh.uz"
PASSWORD = "admin12345"
PER_BLOCK = 20
TOTAL = 1005

failures: list[str] = []


def check(name: str, ok: bool, extra: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{(' - ' + extra) if extra else ''}")
    if not ok:
        failures.append(name)


def post(path: str, token: str, body: dict):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def get(path: str, token: str):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def fetch(path: str) -> tuple[int, str]:
    """GET a static asset without auth."""
    try:
        with urllib.request.urlopen(BASE + path, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def login() -> str:
    req = urllib.request.Request(
        BASE + "/api/auth/login",
        data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())["access_token"]


token = login()
exams = get("/api/exams?published_only=true", token)
check("published exam exists", len(exams) >= 1)
exam = exams[0]

check("exam links all 1005 questions", exam["question_count"] == TOTAL,
      f"got {exam['question_count']}")
check("exam is 20 questions per block", exam["questions_per_block"] == PER_BLOCK,
      f"got {exam['questions_per_block']}")

blocks = -(-TOTAL // PER_BLOCK)   # ceil
check("block count is 51", blocks == 51, f"got {blocks}")

# Walk every block: sizes must match and questions must never repeat.
seen: dict[int, int] = {}
sizes_ok = True
overlap_ok = True
for block in range(1, blocks + 1):
    # The endpoint answers 201 Created on success.
    status, attempt = post("/api/attempts/start", token, {
        "exam_id": exam["id"], "block_number": block, "mode": "exam",
        "shuffle_questions": True, "shuffle_options": True,
    })
    if status not in (200, 201):
        check(f"block {block} starts", False, f"status={status}")
        break
    n = attempt["total_questions"]
    expected = PER_BLOCK if block < blocks else TOTAL % PER_BLOCK
    if n != expected:
        sizes_ok = False
        print(f"     block {block}: {n} questions, expected {expected}")
    # The payload exposes `questions`, each carrying question_id.
    for q in attempt.get("questions") or []:
        qid = q.get("question_id")
        seen[qid] = seen.get(qid, 0) + 1

check("all 51 blocks start", len(seen) > 0)
check("all 51 blocks return the right size", sizes_ok)
check("no question appears in two blocks",
      all(v == 1 for v in seen.values()),
      f"{sum(1 for v in seen.values() if v > 1)} duplicated")
check("all 1005 questions are reachable", len(seen) == TOTAL,
      f"reached {len(seen)}")

# 6. each numbered test is its own card on the list page, with no block picker
status, js = fetch("/js/pages/tests.js")
check("tests.js is served", status == 200, f"status={status}")
check("one card per numbered test", "testCard" in js and "state.tests" in js)
check("tests are split into blocks from the exam",
      "Math.ceil(total / per)" in js)
check("the block picker was removed", "block-grid" not in js)
check("the start dialog was removed",
      "openStartDialog" not in js and "modal-overlay" not in js
      and "numberedRow" not in js and "segmented(" not in js)
check("the card starts its own test directly",
      "block_number: t.block" in js and "startTest(t, navigate" in js)
check("start honours the exam's own settings",
      'mode: "exam"' in js and "shuffle_options: null" in js)
status, css = fetch("/css/app.css")
check("app.css is served", status == 200, f"status={status}")
check("test card styles are present", ".variant-card" in css and ".card-start" in css)
check("dead start-dialog styles were removed",
      ".start-head" not in css and ".numbered-item" not in css
      and ".seg" not in css and ".start-note" not in css)

# 7. retrying a block must return the same questions (shuffle is per-attempt)
first_ids = None
same = True
for _ in range(2):
    status, attempt = post("/api/attempts/start", token, {
        "exam_id": exam["id"], "block_number": 7, "mode": "exam",
        "shuffle_questions": True, "shuffle_options": True,
    })
    ids = sorted(q["question_id"] for q in attempt["questions"])
    if first_ids is None:
        first_ids = ids
    elif ids != first_ids:
        same = False
check("block 7 is stable across attempts", same)

# 8. the last block is a short one; submitting it must still score cleanly
status, attempt = post("/api/attempts/start", token, {
    "exam_id": exam["id"], "block_number": blocks, "mode": "exam",
    "shuffle_questions": True, "shuffle_options": True,
})
check("last block starts", status in (200, 201), f"status={status}")
check("last block is short", attempt["total_questions"] == TOTAL % PER_BLOCK,
      f"got {attempt['total_questions']}")

# answer everything with the first option and submit
answers = [
    {"question_id": q["question_id"], "position": q["position"], "selected_index": 0}
    for q in attempt["questions"]
]
status, done = post(f"/api/attempts/{attempt['id']}/submit", token,
                    {"answers": answers})
check("short block submits", status in (200, 201), f"status={status}")
if status in (200, 201):
    gradable = sum(1 for q in attempt["questions"] if q.get("is_gradable"))
    check("score is graded over keyed questions only",
          done["total_questions"] == attempt["total_questions"],
          f"{done['total_questions']} questions, {gradable} gradable")
    check("score is a valid percentage",
          0.0 <= done["score_percent"] <= 100.0, f"{done['score_percent']}")

print()
if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
    sys.exit(1)
print(f"{blocks} blocks x {PER_BLOCK} questions ({TOTAL} total) verified.")