"""Shared KTO scalar-field cleaning helpers.

Both SPT (detail / related) and MAP (nearby) parse raw KTO API items, so the
trim-empty-to-None logic lives here in core rather than being duplicated per
module. `clean_scalar` is the default; `verbatim` is the exception for KTO
`overview`, which must be stored exactly as sent (ADR-0007).
"""

from __future__ import annotations


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
