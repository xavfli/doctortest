"""Parse the answer-key text file into (number, question, answer) triples.

The file mixes several layouts, so the answer is located by a language-neutral
marker rather than by position:

  Latin   : "  1. **Question text**"  ->  "* **Javob:** answer"
  Cyrillic: "### 1. Question text"    ->  "* **Тўғри жавоб:** answer"

Some entries omit the bullet or the bold markers entirely, so both forms are
accepted. Anything after the marker is the answer, with trailing explanatory
parentheses preserved (they carry the doctor's reasoning, not part of the key).

Writes nothing; import `parse()` from other tools.
"""
from __future__ import annotations

import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_PATH = r"c:\Users\asad2\Downloads\Текстовый документ.txt_Parsing.uz.txt"

# Marker word, in either script, followed by a colon. Matched anywhere in the
# block because both layouts prefix it ("* **Javob:**", " * **Тўғри жавоб:**").
# The Cyrillic half of the file spells the qualifier in Latin ("Toʻgʻri javob:"),
# so that spelling is listed too — otherwise "Toʻgʻri" is left stuck to the end of
# the question text and every comparison loses those characters.
ANSWER_MARKER = re.compile(
    r"(?:Тўғри\s*жавоб"
    r"|toʻgʻri\s*javob"
    r"|tog'ri\s*javob"
    r"|to‘g‘ri\s*javob"
    r"|жавоб"
    r"|Javob)\s*:\s*",
    re.IGNORECASE,
)

# A numbered heading: optional "###", the number, then a dot.
HEADING = re.compile(r"(?m)^\s*(?:#{0,3}\s*)?(\d{1,4})\s*\.\s*")


def clean(text: str) -> str:
    """Strip markdown noise without touching the words themselves."""
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"(?m)^\s*[-*•]\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t*·.:")


def parse(path: str = DEFAULT_PATH) -> list[dict]:
    """Return one dict per numbered entry: {number, question, answer}."""
    text = open(path, "rb").read().decode("utf-8-sig")

    # Split on numbered headings, keeping the number with its block.
    marks = list(HEADING.finditer(text))
    entries: list[dict] = []
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        block = text[start:end]

        marker = ANSWER_MARKER.search(block)
        if not marker:
            entries.append({
                "number": int(m.group(1)),
                "question": clean(block),
                "answer": None,
            })
            continue

        entries.append({
            "number": int(m.group(1)),
            "question": clean(block[:marker.start()]),
            "answer": clean(block[marker.end():]),
        })
    return entries


if __name__ == "__main__":
    rows = parse()
    have = [r for r in rows if r["answer"]]
    print(f"entries      : {len(rows)}")
    print(f"with answer  : {len(have)}")
    print(f"missing      : {len(rows) - len(have)}")
    print()
    for r in rows[:4]:
        print(f"[{r['number']}] Q: {r['question'][:64]}")
        print(f"      A: {(r['answer'] or '—')[:64]}")
    print(" ...")
    for r in rows[-2:]:
        print(f"[{r['number']}] Q: {r['question'][:64]}")
        print(f"      A: {(r['answer'] or '—')[:64]}")