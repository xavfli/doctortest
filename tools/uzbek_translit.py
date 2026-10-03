"""Uzbek Cyrillic to Latin transliteration.

The answer file is Latin for questions 1-362 and Cyrillic for 363-1005, while
the question bank is Latin throughout. Transliterating puts both sides in one
script so they can be compared. Uzbek Cyrillic maps 1:1 onto the Latin alphabet,
so this is mechanical rather than linguistic.
"""
from __future__ import annotations

# Cyrillic -> Latin. Multi-character outputs are joined before the single
# letters, otherwise "ё" would transliterate as "y" + leftover.
_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d",
    "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i", "й": "y",
    "к": "k", "қ": "q", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "x", "ҳ": "h", "ц": "ts", "ч": "ch", "ш": "sh",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ў": "u", "қ": "q",
}

# Punctuation that differs between the two scripts.
_PUNCT = {
    "–": "-", "—": "-", "−": "-", "‑": "-",
    "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
    "…": " ", " ": " ", "’": "'", "ʼ": "'", "ʻ": "'",
    "‘": "'", "ʹ": "'", "‑": "-",
}


def translit(text: str) -> str:
    """Convert Cyrillic letters to their Latin Uzbek equivalents."""
    out: list[str] = []
    for ch in text or "":
        if ch in _CYR:
            out.append(_CYR[ch])
        elif ch in _PUNCT:
            out.append(_PUNCT[ch])
        else:
            out.append(ch)
    return "".join(out)


def to_latin(text: str) -> str:
    """Transliterate Cyrillic and flatten the smart quotes used in the Word file.

    "ʻ"/"ʼ"/"'" all denote the Uzbek apostrophe, so they become one character and
    are removed later by normalisation.
    """
    return translit(text).replace("\u2019", "'").replace("\u02bb", "'")