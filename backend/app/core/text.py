"""Shared KTO scalar-field cleaning. `clean_scalar` trims; `verbatim` preserves `overview` exactly (ADR-0007)."""

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
