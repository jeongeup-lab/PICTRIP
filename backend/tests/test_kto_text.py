from __future__ import annotations

import pytest

from app.kto.text import clean_homepage


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("http://visitkorea.or.kr", "http://visitkorea.or.kr"),
        (
            '<a href="http://www.jeju.go.kr" target="_blank">http://www.jeju.go.kr</a>',
            "http://www.jeju.go.kr",
        ),
        ("<a href='https://example.com'>example</a>", "https://example.com"),
        ('  <a href="https://x.kr">x</a>  ', "https://x.kr"),
        ("<p>visit &amp; stay</p>", "visit & stay"),
        ("seoul &lt;city&gt;", "seoul <city>"),
        ('<a href="">방문</a>', "방문"),
    ],
)
def test_clean_homepage(raw: str | None, expected: str | None) -> None:
    assert clean_homepage(raw) == expected
