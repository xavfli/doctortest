"""Reproduce the router -> page -> API path without a browser.

`app.js` calls every page as `page.render(view, navigate, args)`. A page that
declares its parameters in a different order silently receives the wrong values
— `results.js` once took `(view, attemptId, navigate)`, so the request went out
as "/attempts/function navigate..." and the server answered "Input should be a
valid integer". This checks that every registered page agrees with the router's
argument order, which is the only place that mismatch can be caught.

Run with:  python tools/check_page_signatures.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "js"

# renderOnly() in app.js is the single call site every page goes through.
CALL = re.compile(r"page\.render\(\s*view\s*,\s*(\w+)\s*,\s*(\w+)\s*\)")
# `function name(<params>) {` and `Pages.x = { render: name }`
DEF = re.compile(r"function\s+(\w+)\s*\(([^)]*)\)\s*\{")
BIND = re.compile(r"Pages\.(\w+)\s*=\s*\{\s*render:\s*(\w+)\s*\}")

failures: list[str] = []
checked = 0

app = (WEB / "app.js").read_text(encoding="utf-8")
call = CALL.search(app)
if not call:
    print("FAIL  could not find the page.render(...) call in app.js")
    raise SystemExit(1)
# group(1) is `navigate`, group(2) is `args`; `view` is always first.
router_args = ["view", call.group(1), call.group(2)]
print(f"router calls          : page.render({', '.join(router_args)})")

for path in sorted(WEB.rglob("*.js")):
    text = path.read_text(encoding="utf-8")
    defs = {m.group(1): [p.strip() for p in m.group(2).split(",") if p.strip()]
            for m in DEF.finditer(text)}
    for bind in BIND.finditer(text):
        page_name, func_name = bind.group(1), bind.group(2)
        rel = path.relative_to(ROOT)
        if func_name not in defs:
            print(f"FAIL  {rel}: Pages.{page_name} -> undefined {func_name}()")
            failures.append(page_name)
            continue
        params = defs[func_name]
        checked += 1
        # The leading parameters must line up with what the router passes.
        if params[:2] != router_args[:2]:
            print(f"FAIL  {rel}: {func_name}({', '.join(params)}) does not match "
                  f"the router's ({', '.join(router_args)})")
            failures.append(page_name)
            continue
        # Anything beyond the router's arguments must arrive via `args`, which is
        # an array. A page wanting a bare value must unpack it, never take a
        # positional parameter the router never fills.
        if len(params) > 3:
            print(f"FAIL  {rel}: {func_name}() declares {len(params) - 3} extra "
                  f"parameter(s) the router never passes")
            failures.append(page_name)
            continue
        if len(params) == 3 and params[2] != router_args[2]:
            print(f"FAIL  {rel}: {func_name}() names its third parameter "
                  f"{params[2]!r} but the router passes {router_args[2]!r}")
            failures.append(page_name)
            continue
        print(f"PASS  {rel}: {func_name}({', '.join(params)})")

# The result page must read the attempt id out of `args`, not from a bare
# parameter — that is exactly the bug this check exists for.
res = (WEB / "pages" / "results.js").read_text(encoding="utf-8")
if "args && args[0]" not in res:
    print("FAIL  results.js does not read the attempt id out of `args`")
    failures.append("result-id")

# ...and the URL it builds must be a plain integer, never a function's source.
req = re.search(r'App\.api\.get\("/attempts/"\s*\+\s*([^)]*)\)', res)
if req and "encodeURIComponent" not in req.group(1):
    print(f"FAIL  results.js builds the URL from unescaped {req.group(1)!r}")
    failures.append("result-url")

print()
if failures:
    print(f"{len(failures)} signature problem(s): {', '.join(sorted(set(failures)))}")
    raise SystemExit(1)
print(f"All {checked} page signatures match the router.")