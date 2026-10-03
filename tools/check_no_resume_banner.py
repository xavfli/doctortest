"""Render the tests page server-side checks and assert the banner is gone.

Drives the real API with a real login, then checks that the served JS no longer
contains the resume banner. Catches a stale bundle or a leftover reference.

Run with:  python tools/check_no_resume_banner.py
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
EMAIL = "admin@osh.uz"
PASSWORD = "admin12345"

failures: list[str] = []


def check(name: str, ok: bool, extra: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{(' - ' + extra) if extra else ''}")
    if not ok:
        failures.append(name)


def fetch(path: str, token: str = "") -> tuple[int, str]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = urllib.request.Request(BASE + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


# 1. the served JS must not contain the banner any more
status, js = fetch("/js/pages/tests.js")
check("tests.js is served", status == 200, f"status={status}")

# 2. the summary strip (Urinishlar / O'rtacha ball / ...) must be gone too
for token in ("Yarim qolgan", "resumeCard", "Tashlab qoldirish", "Davom etish"):
    check(f"no {token!r} in tests.js", token not in js)

for token in ("statsRow", "Eng yaxshi", "O‘tganlar", "O‘rtacha ball"):
    check(f"no {token!r} in tests.js", token not in js)

check("no active-attempt request in tests.js",
      '/attempts/active' not in re.sub(r'/\*\*(?:.|\n)*?\*/', '', js))
# the stats strip was the only reason the page fetched attempt history
check("no history request in tests.js", "/attempts/history" not in js)

# 2. login and confirm the API still answers normally
payload = json.dumps({"email": EMAIL, "password": PASSWORD}).encode()
req = urllib.request.Request(
    BASE + "/api/auth/login", data=payload,
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=20) as r:
    token = json.loads(r.read())["access_token"]
check("login works", bool(token))

status, exams = fetch("/api/exams?published_only=true", token)
check("exams list still loads", status == 200, f"status={status}")

status, history = fetch("/api/attempts/history?limit=6", token)
check("history still loads", status == 200, f"status={status}")

# 3. the endpoint itself is untouched — only the UI stopped calling it
status, active = fetch("/api/attempts/active", token)
check("active endpoint still available", status in (200, 404), f"status={status}")

print()
if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("Resume banner removed.")