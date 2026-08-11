from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent import llm, repositories
from app.modules.agent.schemas import AskResponse, QueryIntent
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import geocode as geocode_service
from app.modules.agent.services import resolve as resolve_service
from app.modules.agent.services import retrieve
from app.modules.spots.services import RegionPrefix
from app.web.errors import RateLimited

JEONGEUP = RegionPrefix(prefix="전북특별자치도 정읍시", sido="전북특별자치도")


class _DeadGemini:
    async def generate_json(self, **kwargs: Any) -> Any:
        raise RateLimited()


def _blank_response() -> AskResponse:
    return AskResponse(
        steps=[], answer=[], spots=[], totalCount=0, intent=QueryIntent(), refinements=[]
    )


@pytest.fixture(autouse=True)
def _gemini_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "get_client", lambda: _DeadGemini())


async def test_a_dish_the_region_table_rejects_becomes_a_food_search_not_a_sightseeing_sweep(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_mapping(session, tokens):  # type: ignore[no-untyped-def]
        return {"정읍": JEONGEUP}

    async def fake_scope(session, keywords):  # type: ignore[no-untyped-def]
        return retrieve.CategoryScope(codes=[], matched=[])

    seen: dict[str, Any] = {}

    async def fake_food(session, **kwargs: Any) -> AskResponse:
        seen.update(kwargs)
        return _blank_response()

    monkeypatch.setattr(retrieve, "map_region_tokens_to_prefixes", fake_mapping)
    monkeypatch.setattr(retrieve, "resolve_category_scope", fake_scope)
    monkeypatch.setattr(ask_service, "_ask_for_food", fake_food)

    await ask_service.ask(
        db_session,
        None,
        None,
        question="정읍 삼겹살집",
        lat=None,
        lng=None,
        image_bytes=None,
        image_mime=None,
    )

    assert seen["action"] == "food"
    assert seen["intent"].regionHints == ["정읍"]
    assert seen["intent"].categoryKeywords == ["삼겹살집"]


async def test_a_station_anchors_the_food_search_instead_of_the_users_own_location(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_scope(session, keywords):  # type: ignore[no-untyped-def]
        return retrieve.CategoryScope(codes=[], matched=[])

    async def fake_region(session, *, hints):  # type: ignore[no-untyped-def]
        return retrieve.EMPTY_REGION_SCOPE

    async def fake_resolve(session, kto, places):  # type: ignore[no-untyped-def]
        return []

    async def fake_load(session, content_ids):  # type: ignore[no-untyped-def]
        return {}

    async def fake_locate(session, name, *, region_hint=None):  # type: ignore[no-untyped-def]
        return geocode_service.Located(
            title=name, lat=37.5547, lng=126.9706, source="naver", content_id=None
        )

    seen: dict[str, Any] = {}

    async def fake_around(session, origin, action, **kwargs: Any) -> AskResponse:
        seen["origin"] = origin
        seen["action"] = action
        seen["lat"] = kwargs.get("lat")
        return _blank_response()

    monkeypatch.setattr(retrieve, "resolve_category_scope", fake_scope)
    monkeypatch.setattr(retrieve, "resolve_region_scope", fake_region)
    monkeypatch.setattr(resolve_service, "resolve_places", fake_resolve)
    monkeypatch.setattr(repositories, "load_candidates_by_ids", fake_load)
    monkeypatch.setattr(geocode_service, "locate", fake_locate)
    monkeypatch.setattr(ask_service, "_ask_around", fake_around)

    await ask_service.ask(
        db_session,
        None,
        None,
        question="서울역 근처 맛집",
        lat=37.4979,
        lng=127.0276,
        image_bytes=None,
        image_mime=None,
    )

    assert seen["origin"] == "서울역"
    assert seen["action"] == "food"
    assert seen["lat"] == pytest.approx(37.5547)
