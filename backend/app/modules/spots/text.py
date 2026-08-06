from __future__ import annotations

import html
import re

_ANCHOR_HREF_RE = re.compile(r"""<a\b[^>]*?\bhref\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_BREAK_RE = re.compile(r"<br\s*/?>|</(?:p|div|li)>", re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")


def clean_homepage(raw: str | None) -> str | None:
    if raw is None:
        return None
    text_value = raw.strip()
    if not text_value:
        return None
    match = _ANCHOR_HREF_RE.search(text_value)
    if match:
        href = html.unescape(match.group(1)).strip()
        if href:
            return href
    stripped = html.unescape(_TAG_RE.sub("", text_value)).strip()
    return stripped or None


def to_plain_text(raw: str) -> str:
    spaced = _BREAK_RE.sub(" ", raw)
    stripped = html.unescape(_TAG_RE.sub("", spaced))
    return _SPACE_RE.sub(" ", stripped).strip()


def clean_scalar(value: object) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def verbatim(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)
