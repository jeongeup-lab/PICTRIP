"""Shared KTO scalar-field cleaning. `clean_scalar` trims; `verbatim` preserves `overview` exactly (ADR-0007)."""

from __future__ import annotations

import html
import re

_ANCHOR_HREF_RE = re.compile(r"""<a\b[^>]*?\bhref\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def clean_homepage(raw: str | None) -> str | None:
    """Normalize a KTO ``homepage`` field for display.

    KTO frequently returns the homepage wrapped in an anchor, e.g.
    ``<a href="http://x" target="_blank">http://x</a>``. Return the bare URL:
    the ``href`` when an anchor is present, else the tag-stripped + unescaped
    text. ``None``/empty (after cleaning) collapses to ``None``.
    """
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


def clean_scalar(value: object) -> str | None:
    """Trim a KTO scalar field (homepage/tel/title/image url); empty/missing -> None."""
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def verbatim(value: object) -> str | None:
    """KTO `overview` must be stored exactly as sent — only ''/None collapse to None."""
    if value is None or value == "":
        return None
    return str(value)
