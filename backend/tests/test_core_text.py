"""Unit tests for KTO scalar-field cleaning helpers (app.core.text)."""

from __future__ import annotations

import pytest

from app.core.text import clean_homepage


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        # Bare URL passes through.
        ("http://visitkorea.or.kr", "http://visitkorea.or.kr"),
        # Anchor tag -> extract the href.
        (
            '<a href="http://www.jeju.go.kr" target="_blank">http://www.jeju.go.kr</a>',
            "http://www.jeju.go.kr",
        ),
        # Single-quoted href.
        ("<a href='https://example.com'>example</a>", "https://example.com"),
        # Anchor with surrounding whitespace.
        ('  <a href="https://x.kr">x</a>  ', "https://x.kr"),
        # No anchor, but tags + entities -> strip tags, unescape, return text.
        ("<p>visit &amp; stay</p>", "visit & stay"),
        # Entities only.
        ("seoul &lt;city&gt;", "seoul <city>"),
        # Empty anchor href falls back to stripped text.
        ('<a href="">방문</a>', "방문"),
    ],
)
def test_clean_homepage(raw: str | None, expected: str | None) -> None:
    assert clean_homepage(raw) == expected
