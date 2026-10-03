"""Extract the questions and options from the source .docx.

A .docx is a zip whose `word/document.xml` holds the paragraphs. Options come
through as literal text lines under each question, so this extracts paragraphs
and lets the caller group them.

Run with:  python tools/extract_docx.py
"""
from __future__ import annotations

import re
import sys
import zipfile
from xml.etree import ElementTree

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DOCX = r"c:\Users\asad2\Downloads\Telegram Desktop\Kategoriya test OSH (1).docx"
NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def paragraphs(path: str = DOCX) -> list[str]:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    out: list[str] = []
    for p in root.iter(f"{NS}p"):
        # Join the runs of a paragraph; Word splits words across them.
        parts = [(t.text or "") for t in p.iter(f"{NS}t")]
        text = "".join(parts).strip()
        if text:
            out.append(text)
    return out


def docx_questions(path: str = DOCX) -> list[dict]:
    """Group the Word paragraphs into {index, question, options} records.

    Word stores a question as a stem paragraph followed by one to three option
    paragraphs, and the first option is appended to the stem in the same
    paragraph, separated by a space. A stem is recognised by ending in ':' or
    '?', so a group starts at each stem and runs until the next stem.
    """
    paras = paragraphs(path)
    groups: list[dict] = []
    cur: dict | None = None
    for p in paras:
        if p.rstrip().endswith(":") or p.rstrip().endswith("?"):
            cur = {"question": p.rstrip(), "options": []}
            groups.append(cur)
        elif cur is not None:
            cur["options"].append(p)
    for i, g in enumerate(groups, 1):
        g["index"] = i
    return groups


if __name__ == "__main__":
    lines = paragraphs()
    print("paragraphs:", len(lines))
    print()
    print("--- first 24 non-empty paragraphs ---")
    for line in lines[:24]:
        print(f"  {ascii(line)[:96]}")
    print("...")
    print("--- last 12 ---")
    for line in lines[-12:]:
        print(f"  {ascii(line)[:96]}")

    nums = [i for i, l in enumerate(lines) if re.match(r"^\s*\d{1,4}[\.\)]", l)]
    print()
    print("paragraphs starting with a number:", len(nums))