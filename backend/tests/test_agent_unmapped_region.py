from __future__ import annotations

import pytest
from fakeredis.aioredis import FakeRedis
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.kto.client import get_kto
from app.main import app
from app.modules.agent.schemas import QueryIntent
from app.modules.agent.services import intent as intent_service
from app.modules.agent.services import retrieve


def _override(db_session: AsyncSession) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: FakeRedis(decode_responses=True)
    app.dependency_overrides[get_kto] = lambda: None


async def _seed_a_valley(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO lcls_systm_codes "
            "(lcls_systm3_cd, lcls_systm2_cd, lcls_systm1_cd, lcls_systm3_nm, "
            "lcls_systm2_nm, lcls_systm1_nm) "
            "VALUES ('NA010100', 'NA01', 'NA', '계곡', '자연관광지', '자연') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, "
            "first_image_url, show_flag, mapx, mapy, lcls_systm1, lcls_systm3) "
            "VALUES ('u1', 12, '어느계곡', '부산광역시 사하구 1', "
            "'http://kto/i.jpg', 1, 129.0, 35.1, 'NA', 'NA010100') ON CONFLICT DO NOTHING"
        )
    )


async def _ask(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    asked: QueryIntent,
) -> dict:
    async def fake_intent(question: str, **kw: object) -> QueryIntent:
        return asked

    monkeypatch.setattr(intent_service, "extract_intent", fake_intent)
    _override(db_session)
    try:
        res = await client.post("/v1/agent/ask", json={"question": "아틀란티스 관광지"})
    finally:
        app.dependency_overrides.clear()
    body = res.json()
    data = body.get("data") or {}
    return {
        "status": res.status_code,
        "answer": "".join(part["text"] for part in data.get("answer", [])),
        "tools": [step["tool"] for step in data.get("steps", [])],
        "count": data.get("totalCount", 0),
    }


async def test_a_region_nobody_has_heard_of_is_reported_rather_than_dropped(
    db_session: AsyncSession,
) -> None:
    scope = await retrieve.resolve_region_scope(db_session, hints=["아틀란티스"])

    assert scope.prefixes == []
    assert scope.unmapped == ("아틀란티스",)


async def test_a_real_region_leaves_nothing_unmapped(db_session: AsyncSession) -> None:
    scope = await retrieve.resolve_region_scope(db_session, hints=["제주"])

    assert scope.prefixes
    assert scope.unmapped == ()


async def test_one_bad_hint_beside_a_good_one_keeps_the_good_prefix(
    db_session: AsyncSession,
) -> None:
    scope = await retrieve.resolve_region_scope(db_session, hints=["제주", "아틀란티스"])

    assert scope.prefixes
    assert scope.unmapped == ("아틀란티스",)


async def test_asking_without_a_region_reports_nothing_unmapped(
    db_session: AsyncSession,
) -> None:
    scope = await retrieve.resolve_region_scope(db_session, hints=[])

    assert scope.unmapped == ()


@pytest.mark.integration
async def test_a_region_we_cannot_place_is_asked_about_instead_of_searched_nationwide(
    db_session: AsyncSession, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """지역만 말했는데 그 지역을 모르면, 전국 결과를 주는 건 못 알아들었다는 뜻을 숨긴다."""
    await _seed_a_valley(db_session)

    got = await _ask(client, db_session, monkeypatch, QueryIntent(regionHints=["아틀란티스"]))

    assert got["status"] == 200
    assert "아틀란티스" in got["answer"]
    assert got["count"] == 0
    assert "category_search" not in got["tools"]


@pytest.mark.integration
async def test_a_nationwide_fallback_names_the_region_it_could_not_place(
    db_session: AsyncSession, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed_a_valley(db_session)

    got = await _ask(
        client,
        db_session,
        monkeypatch,
        QueryIntent(regionHints=["아틀란티스"], categoryKeywords=["계곡"]),
    )

    assert got["status"] == 200
    assert got["count"] > 0
    assert "아틀란티스" in got["answer"]


@pytest.mark.integration
async def test_a_landmark_is_never_called_a_region_we_could_not_find(
    db_session: AsyncSession, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """강남역은 실재한다 — 행정구역이 아니라 지역 필터로 못 쓸 뿐이다."""
    await _seed_a_valley(db_session)

    got = await _ask(
        client,
        db_session,
        monkeypatch,
        QueryIntent(regionHints=["강남역"], categoryKeywords=["계곡"]),
    )

    assert "강남역" not in got["answer"]


@pytest.mark.integration
async def test_a_region_we_can_place_says_nothing_about_unmapped_hints(
    db_session: AsyncSession, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed_a_valley(db_session)

    got = await _ask(
        client,
        db_session,
        monkeypatch,
        QueryIntent(regionHints=["부산"], categoryKeywords=["계곡"]),
    )

    assert got["status"] == 200
    assert "못 찾아서" not in got["answer"]
