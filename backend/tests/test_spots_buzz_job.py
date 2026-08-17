from __future__ import annotations

from datetime import date

from app.modules.spots.buzz_job import SpotMention, aggregate_mentions
from app.naver.client import NaverBlogPost

TODAY = date(2026, 8, 17)


def post(
    title: str,
    description: str = "",
    link: str = "https://blog.naver.com/writer-a/1",
    postdate: str = "20260810",
) -> NaverBlogPost:
    return NaverBlogPost(title=title, link=link, description=description, postdate=postdate)


def test_counts_mentions_found_in_title_or_description() -> None:
    candidates = [("c1", "우유부단"), ("c2", "성산일출봉")]
    posts = [
        post("제주 우유부단 아이스크림 후기"),
        post("애월 카페 투어", description="마지막은 우유부단으로 마무리"),
        post("전혀 다른 이야기"),
    ]

    out = {m.content_id: m for m in aggregate_mentions(candidates, posts, today=TODAY)}

    assert out["c1"].mentions == 2
    assert "c2" not in out


def test_distinct_blogs_collapse_posts_from_the_same_author() -> None:
    candidates = [("c1", "우유부단")]
    posts = [
        post("우유부단 1편", link="https://blog.naver.com/adwriter/1"),
        post("우유부단 2편", link="https://blog.naver.com/adwriter/2"),
        post("우유부단 방문기", link="https://blog.naver.com/other/9"),
    ]

    [m] = aggregate_mentions(candidates, posts, today=TODAY)

    assert m.mentions == 3
    assert m.distinct_blogs == 2


def test_recent_ratio_uses_the_90_day_cutoff() -> None:
    candidates = [("c1", "우유부단")]
    posts = [
        post("우유부단 최근", postdate="20260801"),
        post("우유부단 옛날", postdate="20250101"),
    ]

    [m] = aggregate_mentions(candidates, posts, today=TODAY)

    assert m.recent_ratio == 0.5


def test_short_generic_names_are_never_matched() -> None:
    candidates = [("c1", "온"), ("c2", "달")]
    posts = [post("온 세상이 달라졌다")]

    assert aggregate_mentions(candidates, posts, today=TODAY) == []


def test_no_posts_yields_no_rows() -> None:
    assert aggregate_mentions([("c1", "우유부단")], [], today=TODAY) == []


def test_mention_row_shape() -> None:
    [m] = aggregate_mentions([("c1", "우유부단")], [post("우유부단")], today=TODAY)
    assert m == SpotMention(content_id="c1", mentions=1, distinct_blogs=1, recent_ratio=1.0)
