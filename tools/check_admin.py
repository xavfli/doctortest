"""End-to-end check of the Django admin: log in, then walk the pages.

Run with:  python tools/check_admin.py
"""
from __future__ import annotations

import http.cookiejar
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8001"
EMAIL = "admin@osh.uz"
PASSWORD = "admin12345"

jar = http.cookiejar.CookieJar()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def get(path: str, follow: bool = True):
    op = opener if follow else urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar), NoRedirect
    )
    try:
        with op.open(BASE + path, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def post(path: str, data: dict, follow: bool = True):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        BASE + path, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    op = opener if follow else urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar), NoRedirect
    )
    try:
        with op.open(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


failures: list[str] = []


def check(name: str, ok: bool, extra: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{(' - ' + extra) if extra else ''}")
    if not ok:
        failures.append(name)


def csrf(html: str) -> str:
    m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    return m.group(1) if m else ""


def diagnose(html: str) -> str:
    """Pull the exception out of Django's debug page, if there is one."""
    m = re.search(r'<pre class="exception_value">(.*?)</pre>', html, re.S)
    if not m:
        return html[:120].replace("\n", " ")
    val = (m.group(1).replace("&#x27;", "'").replace("&quot;", '"')
           .replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
    frames = re.findall(r'(admin_site/[a-z_/]+\.py)', html)
    return f"{val[:150]} @ {frames[-1] if frames else '?'}"


# 1. login page
status, html = get("/login/")
check("login page renders", status == 200 and "osh-login-card" in html, f"status={status}")

# 2. sign in using the password FastAPI already stored
status, html = post("/login/", {
    "csrfmiddlewaretoken": csrf(html),
    "username": EMAIL,
    "password": PASSWORD,
    "next": "/admin/",
}, follow=False)
check("login accepted (302 redirect)", status == 302, f"status={status} {diagnose(html)}")

status, html = get("/admin/")
check("dashboard renders", status == 200 and "Boshqaruv paneli" in html,
      f"status={status} {diagnose(html)}")
check("back-to-student button present", "O‘quvchi saytiga" in html)
check("stat cards rendered", html.count("osh-stat-label") >= 4,
      f"{html.count('osh-stat-label')} cards")

# 3. every registered model list page
for path, label in [
    ("/admin/users/question/", "questions"),
    ("/admin/users/exam/", "exams"),
    ("/admin/users/adminuser/", "users"),
    ("/admin/users/attempt/", "attempts"),
    ("/admin/users/answer/", "answers"),
    ("/admin/users/appsetting/", "settings"),
    ("/admin/users/auditlog/", "audit logs"),
]:
    status, body = get(path)
    check(f"list page: {label}", status == 200, f"status={status} {diagnose(body)}")

# 4. change form (the password field must stay form-only)
status, body = get("/admin/users/adminuser/1/change/")
check("user change form renders", status == 200, f"status={status} {diagnose(body)}")
check("password field is form-only", "new_password" in body)

# 5. a wrong password must not grant access
jar.clear()
_, html = get("/login/")
post("/login/", {"csrfmiddlewaretoken": csrf(html), "username": EMAIL,
                 "password": "definitely-wrong", "next": "/admin/"})
status, _ = get("/admin/", follow=False)
check("wrong password rejected", status in (302, 301), f"status={status}")

print()
if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("All admin checks passed.")