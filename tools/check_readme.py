"""Check that every fenced code block in the README is closed.

The file is edited from several places (and sometimes through a web editor that
reorders the trailing fence), so an odd number of ``` lines means the rest of
the document renders as one giant code block. Cheap to check, annoying to spot.

Run with:  python tools/check_readme.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
readme = ROOT / "README.md"

text = readme.read_text(encoding="utf-8")
lines = text.splitlines()

fence = "`" * 3
open_line: int | None = None
opens = 0
for number, line in enumerate(lines, 1):
    if not line.strip().startswith(fence):
        continue
    if open_line is None:
        open_line = number
        opens += 1
    else:
        open_line = None

print(f"fenced blocks opened : {opens}")
if open_line is None:
    print("OK - every code block is closed.")
else:
    print(f"BROKEN - a code block opened on line {open_line} is never closed.")
    raise SystemExit(1)