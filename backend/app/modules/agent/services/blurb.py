from __future__ import annotations

import re

MAX_BLURB_CHARS = 62
ELLIPSIS = "…"

_MARKUP = re.compile(r"[<>]")
_SENTENCE_END = re.compile(r"[.!?。](?=\s|$)")


def excerpt(overview: str | None) -> str | None:
    if not overview or _MARKUP.search(overview):
        return None
    original = overview.strip()
    if not original:
        return None
    sentence = _first_sentence(original)
    if len(sentence) <= MAX_BLURB_CHARS:
        return sentence
    return original[:MAX_BLURB_CHARS] + ELLIPSIS


def _first_sentence(original: str) -> str:
    match = _SENTENCE_END.search(original)
    return original[: match.end()] if match else original
