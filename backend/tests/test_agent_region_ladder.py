from __future__ import annotations

from typing import Any

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.schemas import AskContext, AskContextSpot, QueryIntent
from app.modules.agent.services import region as region_service
from app.modules.map.schemas import RegionLabel

SEOUL = {"lat": 37.5665, "lng": 126.9780}


@pytest.fixture
def redis() -> FakeRedis:
    return FakeRedis(decode_responses=True)


def _no_geocode(monkeypatch: pytest.MonkeyPatch) -> list[tuple[float, float]]:
    calls: list[tuple[float, float]] = []

    async def spy(_redis: Any, *, lat: float, lng: float) -> RegionLabel | None:
        calls.append((lat, lng))
        return RegionLabel(
            sido="서울특별시", sigungu="광진구", dong="군자동", label="광진구 군자동"
        )

    monkeypatch.setattr(region_service, "reverse_geocode", spy)
    return calls


async def test_a_region_named_in_the_question_wins_outright(
    db_session: AsyncSession, redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _no_geocode(monkeypatch)

    resolved = await region_service.resolve(
        db_session,
        redis,
        intent=QueryIntent(regionHints=["제주"]),
        context=AskContext(intent=QueryIntent(regionHints=["부산"])),
        **SEOUL,
    )

    assert resolved.hints == ["제주"]
    assert resolved.source == "question"
    assert calls == []


async def test_the_previous_turn_beats_the_phone_because_people_plan_trips_from_home(
    db_session: AsyncSession, redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _no_geocode(monkeypatch)

    resolved = await region_service.resolve(
        db_session,
        redis,
        intent=QueryIntent(),
        context=AskContext(intent=QueryIntent(regionHints=["제주"])),
        **SEOUL,
    )

    assert resolved.hints == ["제주"]
    assert resolved.source == "context"
    assert calls == [], "직전 대화로 정해졌으면 좌표를 물어볼 이유가 없다"


async def test_coordinates_are_the_last_resort_and_are_marked_as_a_guess(
    db_session: AsyncSession, redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_geocode(monkeypatch)

    resolved = await region_service.resolve(
        db_session, redis, intent=QueryIntent(), context=None, **SEOUL
    )

    assert resolved.hints == ["광진구"]
    assert resolved.source == "coords"
    assert resolved.guessed is True
    assert resolved.label == "광진구"


async def test_nothing_is_guessed_when_the_phone_has_no_location(
    db_session: AsyncSession, redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_geocode(monkeypatch)

    resolved = await region_service.resolve(
        db_session, redis, intent=QueryIntent(), context=None, lat=None, lng=None
    )

    assert resolved.hints == []
    assert resolved.source == "none"
    assert resolved.guessed is False


async def test_a_tapped_card_pins_the_region_ahead_of_the_older_conversation(
    db_session: AsyncSession, redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_geocode(monkeypatch)
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, ldong_regn_cd) "
            "VALUES ('9100001', 12, '오동도', '전라남도 여수시', 'http://k/i.jpg', 1, 'NA', NULL)"
        )
    )

    resolved = await region_service.resolve(
        db_session,
        redis,
        intent=QueryIntent(),
        context=AskContext(
            intent=QueryIntent(regionHints=["부산"]),
            focusContentId="9100001",
            spots=[AskContextSpot(contentId="9100001", title="오동도")],
        ),
        **SEOUL,
    )

    assert resolved.source == "context"
