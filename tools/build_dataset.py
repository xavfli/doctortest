"""Parse the PDF (questions + 4 options) and the TXT (correct answers) into one dataset.

Outputs:
  build/questions_pdf.json  - questions/options extracted from PDF
  build/answers_txt.json    - correct answer strings extracted from TXT
"""
import json
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

PDF = r"c:\Users\asad2\Downloads\Telegram Desktop\Kategoriya test OSH.pdf"
TXT = r"c:\Users\asad2\OneDrive\Рабочий стол\Текстовый документ.txt"
OUT = Path(__file__).resolve().parents[1] / "build"
OUT.mkdir(exist_ok=True)

Q_X, OPT_X = 90.5, 129.3
X_TOL = 3.0


# --------------------------------------------------------------------------- pdf
def pdf_rows(reader):
    """Yield (page_index, y, [(x, text), ...]) rows built from text chunks."""
    for pi, page in enumerate(reader.pages):
        parts = []

        def visitor(text, cm, tm, font_dict, font_size, parts=parts):
            if text.strip():
                parts.append((round(tm[4], 1), round(tm[5], 1), text))

        page.extract_text(visitor_text=visitor)
        rows = {}
        for x, y, t in parts:
            key = round(y / 2.0)  # merge chunks with tiny y differences
            rows.setdefault(key, []).append((x, t))
        for key in sorted(rows, reverse=True):
            yield pi, key, sorted(rows[key])


# Leading question numbers sit at x=90.5 (rarely 94.0); options at x>=129.3.
# A row is a question head when its first chunk is a bare number in that column
# AND the row carries text as well (a lone number is a footnote artefact).
NUM_X_MAX = 100.0
NUM_ONLY = re.compile(r"^\d{1,4}$")
# Rows made only of symbols/digits (e.g. '°°', '× 1000') are footnote remnants.
JUNK = re.compile(r"^[^\w]*$", re.UNICODE)


def row_text(chunks):
    out = []
    for x, t in chunks:
        t = t.strip()
        if not t:
            continue
        if out:
            out.append(" " + t)
        else:
            out.append(t)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def parse_pdf():
    reader = PdfReader(PDF)
    questions = []
    cur = None
    mode = None  # "q" | "opt"

    def flush():
        nonlocal cur, mode
        if cur:
            questions.append(cur)
        cur, mode = None, None

    for pi, y, chunks in pdf_rows(reader):
        min_x = min(x for x, _ in chunks)
        texts = [(x, t.strip()) for x, t in chunks if t.strip()]

        # A question head: leading bare number in the number column, and the row
        # also carries text (so lone numbers such as '× 1000' are not heads).
        qid = None
        rest = texts
        if (
            len(texts) > 1
            and texts[0][0] <= NUM_X_MAX
            and NUM_ONLY.match(texts[0][1])
        ):
            qid = int(texts.pop(0)[1])

        if qid is not None:
            # Everything after the number on this row belongs to the question,
            # even if it is indented to the option column.
            flush()
            cur = {
                "id": qid,
                "question": row_text(rest),
                "options": [],
                "page": pi + 1,
            }
            mode = "q"
            continue

        if cur is None:
            continue
        text = row_text(chunks)

        if min_x >= OPT_X - X_TOL:
            # Superscript runs (e.g. 'H2', 'α2') are emitted on a separate line
            # indented deeper than the option column; they continue that option.
            if (
                min_x > OPT_X + X_TOL
                and cur["options"]
                and NUM_ONLY.match(text.split()[0] if text.split() else "")
            ):
                cur["options"][-1] += " " + text
                continue
            if JUNK.match(text):  # footnote remnants like '°°'
                continue
            cur["options"].append(text)
            mode = "opt"
        elif mode == "opt" or (cur["options"] and not cur["question"].rstrip().endswith(":")):
            cur["options"][-1] += " " + text
        else:
            cur["question"] += " " + text
    flush()

    for q in questions:
        q["question"] = re.sub(r"\s+", " ", q["question"]).strip()
        q["options"] = [re.sub(r"\s+", " ", o).strip() for o in q["options"]]
    seen, uniq = set(), []
    for q in sorted(questions, key=lambda q: q["id"]):
        if q["id"] in seen:
            continue
        seen.add(q["id"])
        uniq.append(q)
    return uniq


# --------------------------------------------------------------------------- txt
BLOCK_RE = re.compile(r"^[ \t]*(?:#{1,4}\s*)?(\d{1,4})\s*[.)]\s*", re.M)
# Answer markers in the TXT: "Javob:", "Жавоб:", "Тўғри жавоб:", "жавоб:".
# Answer markers in the source:
#   "Javob:" (Latin half), "Тўғри жавоб:" / "Жавоб:" (Cyrillic half) and a
# misspelled variant "Изҳоб:" that appears in a few blocks.
# Only matched at the start of a line so question wording is never damaged.
ANS_RE = re.compile(
    r"(?:\u0422\u045e\u0493\u0440\u0438\s*)?[\u0436\u0416\u0436\u0438\u0418\u0438][\u0430\u0437]"
    r"[\u0432\u0412][\u043e\u043e][\u0431\u0431\u04b3]?\s*:?\s*"
    r"|\u0418\u0437\u043e\u04b3\s*:?\s*",
    re.UNICODE,
)
# The Latin-script part of the TXT writes the marker as "Javob:".
LATIN_ANS_RE = re.compile(r"Javob\s*:?\s*", re.IGNORECASE)
# A marker that the source repeats inside a single line.
MID_ANS_RE = re.compile(
    r"[\u0416\u0436\u0418\u0438][\u0430\u0437][\u0432\u0412\u0417\u0437][\u043e\u045e][\u0431\u0431\u0441]\s*:?\s*"
)
# Stray markers at the end of a captured answer belong to the *next* question.
TRAIL_RE = re.compile(
    r"\*+\s*(?:\u0422\u045e\u0493\u0440\u0438\s*)?[\u0436\u0416\u0418\u0438]\u0430\u0432\u043e\u0431\s*:?\s*\**\s*$",
    re.IGNORECASE,
)


def parse_txt():
    """Extract answers from the TXT.

    Each block has this shape:
        <question wording>                  (1..n lines)
        <marker>: <note / option label>     (a "definition" line, optional)
        <marker>: <the answer text>         (the real answer)
    The answer is the text after the LAST marker line. In the Cyrillic half the
    marker is written as "Тўғри жавоб:" and also as the typo "Изоб:".
    """
    raw = Path(TXT).read_text(encoding="utf-8-sig")
    blocks = list(BLOCK_RE.finditer(raw))
    out = {}
    for i, m in enumerate(blocks):
        qid = int(m[1])
        body = raw[m.end(): blocks[i + 1].start() if i + 1 < len(blocks) else len(raw)]
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        marker_lines = [
            k
            for k, ln in enumerate(lines)
            if ANS_RE.match(ln.lstrip("* ")) or LATIN_ANS_RE.match(ln.lstrip("* "))
        ]
        if not marker_lines:
            continue
        # The answer is whatever follows the last marker line. Only the leading
        # marker is stripped, so words inside the answer text are preserved.
        parts = []
        for ln in lines[marker_lines[-1]:]:
            bare = ln.lstrip("* ")
            m = ANS_RE.match(bare) or LATIN_ANS_RE.match(bare)
            if m:
                bare = bare[m.end():]
            bare = re.sub(r"\*+", " ", bare)
            if bare.strip():
                parts.append(bare.strip())
        answer = re.sub(r"\s+", " ", " ".join(parts)).strip()
        # Some blocks repeat the marker inside the answer line; keep the tail.
        m = MID_ANS_RE.search(answer)
        if m:
            answer = answer[m.end():].strip()
        out[qid] = answer
    return out

# --------------------------------------------------------------------------- match
# Cyrillic -> Latin transliteration for the letters used in the answers, so a
# Cyrillic answer from the TXT can be matched against a Latin PDF option.
TRANSLIT = {
    "\u0430": "a", "\u0431": "b", "\u0432": "v", "\u0433": "g", "\u0493": "g",
    "\u0434": "d", "\u0435": "e", "\u0451": "e", "\u0456": "z", "\u0436": "j",
    "\u0437": "z", "\u0438": "i", "\u0439": "y", "\u043a": "k", "\u049b": "q",
    "\u043b": "l", "\u043c": "m", "\u043d": "n", "\u043e": "o", "\u043f": "p",
    "\u0440": "r", "\u0441": "s", "\u0442": "t", "\u0443": "u", "\u0443": "u",
    "\u0444": "f", "\u0445": "x", "\u0446": "c", "\u0447": "ch", "\u0448": "sh",
    "\u0449": "sh", "\u044a": "", "\u044b": "y", "\u044c": "", "\u044d": "e",
    "\u044e": "yu", "\u044f": "ya", "\u045e": "u", "\u04b3": "h",
}


# Uzbek Latin letters that the PDF uses but that do not exist in pure Latin:
# "o'" -> "o", "g'" -> "g", "yo'" -> "yo", etc. Handled inside norm().
def norm(s):
    """Lowercase and drop punctuation so PDF text and TXT text compare equal.

    Two sources are mixed here: the PDF is in Latin script while part of the
    TXT is in Cyrillic, so the same word can appear as "faringit" / "фарингит".
    A transliteration table maps the Cyrillic letters onto their Latin
    counterparts, and Uzbek digraphs are folded so both sides look alike.
    """
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[\u02bb\u02bc\u02b9\u02bd\u02b8\u02c8\u2032\u2018\u2019]", "'", s)
    s = re.sub(r"[\"\"\u00ab\u00bb]", "", s)
    # Drop answer-marker words before tokenising.
    s = MID_ANS_RE.sub(" ", s)
    s = re.sub(r"\bjava?b\b", " ", s)
    for cyr, lat in TRANSLIT.items():
        s = s.replace(cyr, lat)
    # Fold Uzbek digraphs so "yo'" == "yo" == "йо".
    s = re.sub(r"([a-z])'", r"\1", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def clean_answer(ans):
    """Remove markdown emphasis, stray markers and trailing explanations."""
    notes = []

    def grab(m):
        notes.append(m.group(1).strip())
        return " "

    # Remove the leading marker of the captured text, and any later marker the
    # source repeats inside the same line.
    ans = re.sub(r"^\**\s*", "", ans)
    ans = re.sub(r"^\**\s*(?:\u0422\u045e\u0493\u0440\u0438\s*)?[\u0436\u0416\u0436\u0438][\u0430\u0437][\u0432\u0412\u0417\u0437][\u043e\u045e][\u0431\u0431\u0441]\s*:?\s*", " ", ans)
    ans = LATIN_ANS_RE.match(ans) and ans[LATIN_ANS_RE.match(ans).end():] or ans
    ans = re.sub(r"\*+", " ", ans)
    core = re.sub(r"\*\((.*?)\)\*", grab, ans)
    core = re.sub(r"\s*\(Chunki.*$", "", core, flags=re.I)
    core = re.sub(r"\s*\(Aslida.*$", "", core, flags=re.I)
    core = re.sub(r"\s*\(Xato fikr.*$", "", core, flags=re.I)
    core = re.sub(r"\s*\(Xurujdan.*$", "", core, flags=re.I)
    core = re.sub(r"\s+", " ", core).strip(" *\u2014-")
    return core, " ".join(notes).strip()


SPLIT_ALT = re.compile(r"\s+(?:Yoki|Як|или)\s+", re.I)

TXT_QUESTION_CACHE = {}


def txt_question_text(qid):
    """Question wording taken from the TXT for questions missing in the PDF."""
    if not TXT_QUESTION_CACHE:
        raw = Path(TXT).read_text(encoding="utf-8-sig")
        blocks = list(BLOCK_RE.finditer(raw))
        for i, m in enumerate(blocks):
            end = blocks[i + 1].start() if i + 1 < len(blocks) else len(raw)
            body = raw[m.end(): end]
            lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
            marker_lines = [
                k
                for k, ln in enumerate(lines)
                if ANS_RE.match(ln.lstrip("* ")) or LATIN_ANS_RE.match(ln.lstrip("* "))
            ]
            head = lines[: marker_lines[0]] if marker_lines else lines
            q = re.sub(r"\*+", " ", " ".join(head)).replace("\u8def\u5f84", "")
            q = re.sub(r"\s+", " ", q).strip().strip(":").strip()
            TXT_QUESTION_CACHE[int(m[1])] = q
    return TXT_QUESTION_CACHE.get(qid, "")


def resolve_index(q, raw_answer):
    """Find which option the TXT answer refers to. Returns (index, notes, score)."""
    core, notes = clean_answer(raw_answer)
    # Some blocks keep the question wording in front of the answer, separated
    # by a leftover marker; keep only the text after the last one.
    parts = MID_ANS_RE.split(core)
    if len(parts) > 1:
        core = parts[-1].strip()
    candidates = [c.strip() for c in SPLIT_ALT.split(core) if c.strip()]
    target = norm(candidates[0])
    if not target:
        return None, notes, 0.0

    opt_norms = [norm(o) for o in q["options"]]
    exact = [i for i, o in enumerate(opt_norms) if o and o == target]
    if exact:
        return exact[0], notes, 1.0
    # "barcha javoblar to'g'ri" is itself one of the options in this test bank.
    if "barcha javob" in target or "барча жавоб" in target:
        allopt = [
            i for i, o in enumerate(opt_norms)
            if "barcha javob" in o or "барча жавоб" in o
        ]
        return (allopt[0] if len(allopt) == 1 else None), notes, 1.0
    contained = [
        i
        for i, o in enumerate(opt_norms)
        if o and (o in target or target in o)
    ]
    if len(contained) == 1:
        return contained[0], notes, 0.9
    # Superscripts split words in the PDF ("reg idron" vs "regidron").
    compact = [o.replace(" ", "") for o in opt_norms]
    tcompact = target.replace(" ", "")
    squashed = [i for i, c in enumerate(compact) if c and c == tcompact]
    if len(squashed) == 1:
        return squashed[0], notes, 0.85
    # fall back to best token overlap
    tw = set(target.split())
    best, score = None, 0.0
    for i, o in enumerate(opt_norms):
        ow = set(o.split())
        if not ow:
            continue
        s = len(tw & ow) / max(1, len(tw | ow))
        if s > score:
            best, score = i, s
    return best, notes, score


def main():
    qs = parse_pdf()
    answers = parse_txt()
    by_id = {q["id"]: q for q in qs}

    # The TXT numbering drifts in places: an answer can end up attached to the
    # next question. Build a pool of all answers so such a card can borrow the
    # answer that actually matches one of its options.
    pool = []
    for qid, raw in answers.items():
        core, _ = clean_answer(raw)
        parts = SPLIT_ALT.split(core)
        t = norm(MID_ANS_RE.split(parts[0])[-1]) if parts else ""
        if t and "barcha javob" not in t:
            pool.append(t)
    pool_set = set(pool)
    pool_compact = {p.replace(" ", "") for p in pool}

    # A question whose own TXT answer does not match any option has drifted:
    # the source numbers are shifted. Search ALL answers in the document for
    # the one that matches this question's options, preferring a neighbour
    # (+/- window) before falling back to the whole pool.
    answer_owner = {}  # normalised option text -> question id that answered it
    for qid, raw in answers.items():
        if qid not in by_id:
            continue
        idx, _, sc = resolve_index(by_id[qid], raw)
        if idx is not None and sc >= 0.85:
            answer_owner[norm(by_id[qid]["options"][idx])] = qid

    def neighbour_lookup(q, window=40):
        for i, opt in enumerate(q["options"]):
            o = norm(opt)
            if not o:
                continue
            owner = answer_owner.get(o) or answer_owner.get(o.replace(" ", ""))
            if owner is not None and abs(owner - q["id"]) <= window:
                return i
        for i, opt in enumerate(q["options"]):
            o = norm(opt)
            if o and (o in pool_set or o.replace(" ", "") in pool_compact):
                return i
        return None

    # In the Cyrillic half of the TXT the answers are shifted: the answer text
    # written under number N answers a DIFFERENT question. Recover the mapping
    # by matching each answer back to the question it actually belongs to, then
    # look up this question's answer in that map.
    q_norm = {q["id"]: norm(q["question"]) for q in qs}
    q_words = {qid: set(t.split()) for qid, t in q_norm.items()}
    answer_to_qid = {}
    for qid, raw in answers.items():
        core, _ = clean_answer(raw)
        parts = SPLIT_ALT.split(core)
        target = norm(MID_ANS_RE.split(parts[0])[-1]) if parts else ""
        if not target:
            continue
        tw = set(target.split())
        best, best_s = None, 0.0
        for other, ow in q_words.items():
            if not ow:
                continue
            # The answer of a question usually repeats words of the question.
            s = len(tw & ow) / max(1, len(tw | ow))
            if s > best_s:
                best, best_s = other, s
        if best is not None and best_s >= 0.12:
            answer_to_qid.setdefault(target, best)
    # Invert: question id -> normalised answer text.
    qid_answer = {}
    for target, owner in answer_to_qid.items():
        qid_answer.setdefault(owner, target)

    dataset = []
    unresolved = []
    repaired_count = 0
    for qid in range(1, 1006):
        raw = answers.get(qid, "")
        if not raw:
            continue
        q = by_id.get(qid)
        if q is None:
            # present in the TXT only: keep it as an open-answer card
            dataset.append(
                {
                    "id": qid,
                    "question": txt_question_text(qid),
                    "options": [],
                    "answer": clean_answer(raw)[0],
                    "notes": clean_answer(raw)[1],
                    "repaired": False,
                    "has_options": False,
                }
            )
            continue
        idx, notes, score = resolve_index(q, raw)
        repaired = False
        answer_all = idx is None and score >= 1.0
        if idx is None and not answer_all:
            # Use the recovered mapping: the answer for this question may have
            # been written under another number in the source.
            recovered = qid_answer.get(qid)
            if recovered:
                for i, opt in enumerate(q["options"]):
                    o = norm(opt)
                    if o and (o == recovered or o.replace(" ", "") == recovered.replace(" ", "")):
                        idx, score, repaired = i, 1.0, True
                        break
        if idx is None and not answer_all:
            found = neighbour_lookup(q)
            if found is not None:
                idx, score, repaired = found, 1.0, True
        if repaired:
            repaired_count += 1
        if idx is None and not answer_all:
            unresolved.append((qid, round(score, 2), raw[:70]))
        # Questions whose answer the source never provides are still playable
        # but are not graded; the UI hides the correct option and says so.
        dataset.append(
            {
                "id": qid,
                "question": q["question"],
                "options": q["options"],
                "answer_index": idx,
                "answer_all": answer_all,
                "answer": (
                    q["options"][idx] if idx is not None else clean_answer(raw)[0]
                ),
                "notes": notes,
                "repaired": repaired,
                "has_options": True,
            }
        )

    (OUT / "questions.json").write_text(
        json.dumps(dataset, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    # Also emit a plain JS file so index.html can be opened with file://
    # (fetch() of a local JSON is blocked by browsers).
    web_dir = Path(__file__).resolve().parents[1] / "web"
    web_dir.mkdir(exist_ok=True)
    (web_dir / "questions.js").write_text(
        "window.QUESTIONS = " + json.dumps(dataset, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print("dataset size:", len(dataset))
    print("with options:", sum(1 for d in dataset if d["has_options"]))
    print("open-answer cards:", sum(1 for d in dataset if not d["has_options"]))
    print("repaired cards:", repaired_count)
    print("unresolved answers:", len(unresolved))
    (OUT / "unresolved.json").write_text(
        json.dumps([r[0] for r in unresolved], indent=1), encoding="utf-8"
    )
    weak = [
        (d["id"], d["notes"][:40])
        for d in dataset
        if d["has_options"] and d.get("answer_index") is None
    ]
    print("questions without resolved option index:", len(weak), weak[:20])


if __name__ == "__main__":
    main()
