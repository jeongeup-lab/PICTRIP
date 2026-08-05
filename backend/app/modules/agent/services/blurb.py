from __future__ import annotations

import re

MAX_BLURB_CHARS = 62
ELLIPSIS = "…"

_MARKUP = re.compile(r"[<>]")
_WHITESPACE = re.compile(r"\s+")
_SENTENCE_END = re.compile(r"[.!?。](?=\s|$)")


def excerpt(overview: str | None) -> str | None:
    if not overview or _MARKUP.search(overview):
        return None
    cleaned = _WHITESPACE.sub(" ", overview).strip()
    if not cleaned:
        return None
    sentence = _first_sentence(cleaned)
    if len(sentence) <= MAX_BLURB_CHARS:
        return sentence
    return cleaned[:MAX_BLURB_CHARS].rstrip() + ELLIPSIS


def _first_sentence(cleaned: str) -> str:
    match = _SENTENCE_END.search(cleaned)
    return cleaned[: match.end()] if match else cleaned
