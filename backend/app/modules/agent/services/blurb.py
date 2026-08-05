from __future__ import annotations

import re

_MARKUP = re.compile(r"[<>]")
_SENTENCE_END = re.compile(r"[.!?。](?=\s|$)")


def excerpt(overview: str | None) -> str | None:
    if not overview or _MARKUP.search(overview):
        return None
    original = overview.strip()
    if not original:
        return None
    match = _SENTENCE_END.search(original)
    return original[: match.end()] if match else original
