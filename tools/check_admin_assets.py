"""Check the admin panel is actually styled and free of leaked template text.

Two regressions are covered:
  * static files 404 when DEBUG is off and nothing serves them, which leaves the
    panel completely unstyled;
  * Django's {# #} comment syntax is single-line only, so a multi-line note
    written with it is rendered as visible page text.

Run with:  python tools/check_admin_assets.py
"""
from __future__ import annotations

import http.cookiejar
import re
import sys
import urllib.parse
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8001"
EMAIL = "admin@osh.uz"
PASSWORD = "admin12345"

failures: list[str] = []


def check(name: str, ok: bool, extra: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{(' - ' + extra) if extra else ''}")
    if not ok:
        failures.append(name)


jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def get(path: str) -> tuple[int, str]:
    try:
        with opener.open(BASE + path, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


# --- static assets must be served, whatever DEBUG is set to ---------------
for asset in ("/static/unfold/css/styles.css", "/static/admin_custom.css"):
    status, body = get(asset)
    check(f"asset served: {asset}", status == 200 and len(body) > 500,
          f"status={status} size={len(body)}")

# --- sign in -------------------------------------------------------------
_, html = get("/login/")
token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)
body = urllib.parse.urlencode({
    "csrfmiddlewaretoken": token, "username": EMAIL,
    "password": PASSWORD, "next": "/admin/",
}).encode()
opener.open(urllib.request.Request(
    BASE + "/login/", data=body,
    headers={"Content-Type": "application/x-www-form-urlencoded"}))

pages = {
    "dashboard": "/admin/",
    "questions": "/admin/users/question/",
    "users": "/admin/users/adminuser/",
    "login": "/login/",
}

for label, path in pages.items():
    status, page = get(path)
    check(f"{label} renders", status == 200, f"status={status}")

    # The stylesheet must actually be referenced. With the manifest storage in
    # place WhiteNoise rewrites it to a fingerprinted name
    # (admin_custom.<hash>.css), so match on the stem rather than the path.
    check(f"{label} links the theme", "unfold/css/styles" in page)
    # With manifest storage WhiteNoise rewrites our stylesheet to a
    # fingerprinted name (admin_custom.<hash>.css), so match the stem.
    check(f"{label} links our stylesheet", "admin_custom." in page)

    # Template comments must not leak into the output.
    leaked = [s for s in ("{#", "{# Overrides", "Vendored from", "Django's {# #}")
              if s in page]
    check(f"{label} has no template comment text", not leaked, str(leaked[:2]))

    # Markup should be Unfold's, not a bare unstyled list.
    check(f"{label} uses the Unfold layout",
          ("unfold" in page.lower() and ("x-data" in page or "sidebar" in page.lower())))

# --- dashboard specifics -------------------------------------------------
_, dash = get("/admin/")
check("dashboard cards render", dash.count("osh-stat-label") >= 6,
      f"{dash.count('osh-stat-label')} cards")
check("back-to-student link present", "osh-back-top" in dash)
check("larger-type class applied", "osh-bigger" in dash)

print()
if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("Admin assets and templates are clean.")