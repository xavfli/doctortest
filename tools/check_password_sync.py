"""Verify that a password set in Django is accepted by the FastAPI API.

Runs a full round trip: change the admin password through the Unfold form,
then log in through the student API with the new value. That is the only real
proof the two apps agree on the PBKDF2 format — and it restores the original
password afterwards, so the demo credentials stay valid.

Run with:  python tools/check_password_sync.py
"""
from __future__ import annotations

import http.cookiejar
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ADMIN = "http://127.0.0.1:8001"
API = "http://127.0.0.1:8000"
EMAIL = "admin@osh.uz"
ORIGINAL = "admin12345"
TEMP = "SyncTest-9182!"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

failures: list[str] = []


def check(name: str, ok: bool, extra: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{(' - ' + extra) if extra else ''}")
    if not ok:
        failures.append(name)


def get(path: str):
    try:
        with opener.open(ADMIN + path, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def post_admin(path: str, data: dict):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        ADMIN + path, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with opener.open(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def api_login(password: str) -> int:
    payload = json.dumps({"email": EMAIL, "password": password}).encode()
    req = urllib.request.Request(
        API + "/api/auth/login", data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def csrf(html: str) -> str:
    m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    return m.group(1) if m else ""


def change_password(new_password: str, current: str) -> tuple[int, str]:
    """Log in as `current`, then set `new_password` through the Unfold form.

    Each call starts a fresh session: the admin redirects to the login page
    after a successful save, so reusing the old cookie would POST as nobody.
    """
    jar.clear()
    _, html = get("/login/")
    post_admin("/login/", {
        "csrfmiddlewaretoken": csrf(html), "username": EMAIL,
        "password": current, "next": "/admin/",
    })
    _, html = get("/admin/users/adminuser/1/change/")
    data = {
        "csrfmiddlewaretoken": csrf(html),
        "email": EMAIL,
        "full_name": "Administrator",
        "role": "admin",
        "is_active": "on",
        "new_password": new_password,
        "_save": "Save",
    }
    return post_admin("/admin/users/adminuser/1/change/", data)


# 1. baseline: the current password must work in both apps
check("API accepts the original password", api_login(ORIGINAL) == 200)

# 2. set a new password through the Unfold form
status, html = change_password(TEMP, ORIGINAL)
check("Django password change accepted", status == 200, f"status={status}")

# 3. the new password must work in the FastAPI API
check("API accepts the new password", api_login(TEMP) == 200)
check("API rejects the old password", api_login(ORIGINAL) == 401)

# 4. restore the demo credentials
status, _ = change_password(ORIGINAL, TEMP)
check("original password restored", api_login(ORIGINAL) == 200, f"status={status}")
check("temp password no longer works", api_login(TEMP) == 401)

print()
if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("Password sync verified in both directions.")