from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent import kakao_places
from app.modules.agent.kakao_places import KakaoPlace
from app.modules.agent.services import places as places_service
from app.naver.client import NaverBlogPost

GUNJA = (37.5573, 127.0794)


def _place(pid: str, name: str, *, lat: float = 37.5573, lng: float = 127.0794) -> KakaoPlace:
    return KakaoPlace(
        place_id=pid,
        name=name,
        category="음식점 > 카페",
        address="서울 광진구 군자동",
        phone="02-000-0000",
        url=f"http://place.map.kakao.com/{pid}",
        lat=lat,
        lng=lng,
        distance_m=240,
    )


def _post(blogger: str, text_: str) -> NaverBlogPost:
    return NaverBlogPost(
        title=text_, link=f"https://blog.naver.com/{blogger}/1", description="", postdate="20260801"
    )


def test_a_name_in_two_different_blogs_counts_twice_as_a_single_blog_spamming_it() -> None:
    places = [_place("1", "사유"), _place("2", "롬곡")]
    posts = [
        _post("aaa", "군자동 사유 카공 후기"),
        _post("bbb", "사유 다녀왔어요"),
        _post("ccc", "롬곡 갔다옴"),
        _post("ccc", "롬곡 또 갔다옴"),
    ]

    counted = places_service.count_mentions(places, posts)

    assert counted["1"].distinct_blogs == 2
    assert counted["2"].distinct_blogs == 1, "같은 블로거가 두 번 써도 한 곳이다"
    assert counted["2"].total == 2


def test_a_place_nobody_wrote_about_gets_no_mention_rather_than_a_zero_row() -> None:
    counted = places_service.count_mentions([_place("9", "아무도안감")], [_post("a", "다른 곳")])

    assert counted == {}


@pytest.fixture
def _kakao(monkeypatch: pytest.MonkeyPatch) -> list[KakaoPlace]:
    found = [_place("1", "사유"), _place("2", "롬곡"), _place("3", "무명카페")]

    async def nearby(*_a: Any, **_k: Any) -> list[KakaoPlace]:
        return found

    async def keyword(*_a: Any, **_k: Any) -> list[KakaoPlace]:
        return found

    monkeypatch.setattr(kakao_places, "search_nearby", nearby)
    monkeypatch.setattr(kakao_places, "search_by_keyword", keyword)
    return found


def _blogs(monkeypatch: pytest.MonkeyPatch, posts: list[NaverBlogPost]) -> None:
    async def fake(_query: str) -> list[NaverBlogPost]:
        return posts

    monkeypatch.setattr(places_service, "_blog_posts", fake)


async def test_kakao_only_places_come_back_as_cards_that_admit_they_cannot_be_saved(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, _kakao: list[KakaoPlace]
) -> None:
    _blogs(monkeypatch, [_post("a", "사유 좋아요"), _post("b", "사유 카공"), _post("c", "롬곡")])

    cards = await places_service.search(
        db_session,
        kind="cafe",
        region="서울특별시 광진구",
        landmark_coords=GUNJA,
        dish=None,
        attribute="카공",
    )

    assert cards, "카카오가 준 곳은 버리지 않는다"
    assert all(card.source == "kakao" for card in cards)
    assert all(card.saveable is False for card in cards)
    assert all(card.contentId.startswith("kakao:") for card in cards)
    assert cards[0].title == "사유", "서로 다른 블로그 2곳이 언급한 곳이 앞에 온다"
    assert cards[0].tag == "블로그 2곳"


async def test_a_kakao_place_that_already_exists_in_our_data_is_promoted_to_a_full_card(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, _kakao: list[KakaoPlace]
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, lcls_systm2, mapx, mapy) VALUES "
            "('9200001', 39, '사유', '서울특별시 광진구 군자동', 'http://kto/i.jpg', 1, "
            "'FD', 'FD05', :lng, :lat)"
        ),
        {"lat": GUNJA[0], "lng": GUNJA[1]},
    )
    _blogs(monkeypatch, [_post("a", "사유 좋아요"), _post("b", "사유 카공")])

    cards = await places_service.search(
        db_session,
        kind="cafe",
        region="서울특별시 광진구",
        landmark_coords=GUNJA,
        dish=None,
        attribute="카공",
    )

    promoted = [card for card in cards if card.source == "kto"]
    assert len(promoted) == 1
    assert promoted[0].contentId == "9200001"
    assert promoted[0].saveable is True
    assert promoted[0].imageUrl is not None
    assert promoted[0].externalUrl is not None, "승격돼도 카카오맵 링크는 남긴다"


async def test_a_same_named_place_far_away_is_not_mistaken_for_the_one_kakao_found(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, _kakao: list[KakaoPlace]
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, lcls_systm2, mapx, mapy) VALUES "
            "('9200002', 39, '사유', '제주특별자치도 제주시', 'http://kto/i.jpg', 1, "
            "'FD', 'FD05', 126.5312, 33.4996)"
        )
    )
    _blogs(monkeypatch, [_post("a", "사유 좋아요"), _post("b", "사유 카공")])

    cards = await places_service.search(
        db_session,
        kind="cafe",
        region="서울특별시 광진구",
        landmark_coords=GUNJA,
        dish=None,
        attribute="카공",
    )

    assert all(card.source == "kakao" for card in cards)
