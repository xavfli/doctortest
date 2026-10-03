"""Grade a few real attempts to prove the imported keys are used correctly.

Picks a block, submits the correct option for every gradable question (and a
wrong one for the rest), and checks the score comes back 100%. Then submits the
same block with everything shifted by one option and checks it is not 100%.
That catches a key stored against the wrong question.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE = "http://127.0.0.1:8000"
DB = ROOT / "data" / "app.db"
EMAIL = "admin@osh.uz"
PASSWORD = "admin12345"

failures: list[str] = []


def check(name: str, ok: bool, extra: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{(' - ' + extra) if extra else ''}")
    if not ok:
        failures.append(name)


def post(path: str, token: str, body: dict):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


req = urllib.request.Request(
    BASE + "/api/auth/login",
    data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=25) as r:
    token = json.loads(r.read())["access_token"]

_, exams = (lambda: (
    200,
    json.loads(urllib.request.urlopen(urllib.request.Request(
        BASE + "/api/exams?published_only=true",
        headers={"Authorization": f"Bearer {token}"}), timeout=25).read()),
))()
exam = exams[0]

con = sqlite3.connect(DB)
keys = {
    qid: (json.loads(opts or "[]"), idx)
    for qid, opts, idx in con.execute(
        "SELECT id, options, answer_index FROM questions "
        "WHERE answer_index IS NOT NULL AND is_active=1"
    )
}
con.close()

tested = 0
for block in (1, 12, 30, 51):
    status, attempt = post("/api/attempts/start", token, {
        "exam_id": exam["id"], "block_number": block, "mode": "exam",
        "shuffle_questions": True, "shuffle_options": True,
    })
    if status not in (200, 201):
        check(f"block {block} starts", False, f"status={status}")
        continue

    qs = attempt["questions"]
    gradable = [q for q in qs if q["question_id"] in keys]
    if not gradable:
        continue

    # The payload reports the shuffled display order; answer_index is the
    # original index, so convert it back before submitting.
    order_map = {}
    for q in gradable:
        opts, idx = keys[q["question_id"]]
        order_map[q["question_id"]] = q["options"].index(opts[idx])

    answers = [
        {"question_id": q["question_id"], "position": q["position"],
         "selected_index": order_map[q["question_id"]]}
        for q in gradable
    ]
    wrong = [
        {"question_id": q["question_id"], "position": q["position"],
         "selected_index": (order_map[q["question_id"]] + 1) % len(q["options"])}
        for q in gradable
    ]

    status, right = post(f"/api/attempts/{attempt['id']}/submit", token,
                         {"answers": answers})
    ok100 = status in (200, 201) and right.get("score_percent") == 100.0
    check(f"block {block}: correct answers score 100%",
          ok100, f"got {right.get('score_percent')}")

    status, attempt2 = post("/api/attempts/start", token, {
        "exam_id": exam["id"], "block_number": block, "mode": "exam",
        "shuffle_questions": True, "shuffle_options": True,
    })
    qs2 = attempt2["questions"]
    om2 = {}
    for q in qs2:
        if q["question_id"] in keys:
            opts, idx = keys[q["question_id"]]
            om2[q["question_id"]] = q["options"].index(opts[idx])
    wrong2 = [
        {"question_id": q["question_id"], "position": q["position"],
         "selected_index": (om2[q["question_id"]] + 1) % len(q["options"])}
        for q in qs2 if q["question_id"] in keys
    ]
    status, bad = post(f"/api/attempts/{attempt2['id']}/submit", token,
                       {"answers": wrong2})
    check(f"block {block}: shifted answers do not score 100%",
          status in (200, 201) and bad.get("score_percent") != 100.0,
          f"got {bad.get('score_percent')}")
    tested += 1

print()
if not tested:
    print("No gradable questions were found in the tested blocks.")
    sys.exit(1)
if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
    sys.exit(1)
print(f"Grading verified across {tested} blocks.")