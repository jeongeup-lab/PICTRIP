from __future__ import annotations

import re

_TERMINATOR = re.compile(r"[.!?](?=\s|$)")


def first_sentence(text: str | None) -> str | None:
    if text is None:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    match = _TERMINATOR.search(stripped)
    return stripped[: match.end()] if match else stripped
