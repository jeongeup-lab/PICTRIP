from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.agent import llm, repositories
from app.modules.agent.schemas import (
    AnchorAction,
    AskAnchor,
    AskContext,
    AskResponse,
    AskStep,
    QueryIntent,
    ResolvedPlace,
)
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import food as food_service
from app.modules.agent.services import geocode as geocode_service
from app.modules.agent.services import intent as intent_service
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

    seen_action: str | None = None
    seen_intent: QueryIntent | None = None
    seen_title_terms: list[str] | None = None

    async def fake_food(
        session: AsyncSession,
        *,
        action: AnchorAction,
        intent: QueryIntent,
        steps: list[AskStep],
        lat: float | None,
        lng: float | None,
        context: AskContext | None,
        resolved: list[ResolvedPlace],
        title_terms: list[str],
    ) -> AskResponse:
        nonlocal seen_action, seen_intent, seen_title_terms
        seen_action = action
        seen_intent = intent
        seen_title_terms = title_terms
        return _blank_response()

    monkeypatch.setattr(retrieve, "map_region_tokens_to_prefixes", fake_mapping)
    monkeypatch.setattr(retrieve, "resolve_category_scope", fake_scope)
    monkeypatch.setattr(ask_service, "ask_for_food", fake_food)

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

    assert seen_action == "food"
    assert seen_intent is not None
    assert seen_intent.regionHints == ["정읍"]
    assert seen_intent.categoryKeywords == ["삼겹살집", "삼겹살"]
    assert seen_title_terms == ["삼겹살"]


async def test_raw_dish_evidence_repairs_a_healthy_generic_food_intent(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_extract(question: str) -> QueryIntent:
        return QueryIntent(categoryKeywords=["맛집"], regionHints=["정읍"])

    async def fake_mapping(session: AsyncSession, tokens: set[str]) -> dict[str, RegionPrefix]:
        return {"정읍": JEONGEUP}

    async def fake_scope(session: AsyncSession, keywords: list[str]) -> retrieve.CategoryScope:
        return retrieve.CategoryScope(codes=[], matched=[])

    seen_intent: QueryIntent | None = None
    seen_title_terms: list[str] | None = None

    async def fake_food(
        session: AsyncSession,
        *,
        action: AnchorAction,
        intent: QueryIntent,
        steps: list[AskStep],
        lat: float | None,
        lng: float | None,
        context: AskContext | None,
        resolved: list[ResolvedPlace],
        title_terms: list[str],
    ) -> AskResponse:
        nonlocal seen_intent, seen_title_terms
        seen_intent = intent
        seen_title_terms = title_terms
        return _blank_response()

    monkeypatch.setattr(intent_service, "extract_intent", fake_extract)
    monkeypatch.setattr(retrieve, "map_region_tokens_to_prefixes", fake_mapping)
    monkeypatch.setattr(retrieve, "resolve_category_scope", fake_scope)
    monkeypatch.setattr(ask_service, "ask_for_food", fake_food)

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

    assert seen_intent is not None
    assert seen_intent.categoryKeywords == ["맛집", "삼겹살"]
    assert seen_title_terms == ["삼겹살"]


@pytest.fixture(autouse=True)
def _gemini_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """이 파일은 Gemini 경로를 겨냥한다 — 기본 프로바이더(DeepSeek)에 기대지 않는다."""
    monkeypatch.setattr(llm, "settings", Settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="k"))


@pytest.mark.parametrize("prior_keyword", ["계곡", "국밥"])
async def test_focused_dish_followup_replaces_carried_category_when_gemini_is_down(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, prior_keyword: str
) -> None:
    seen_action: AnchorAction | None = None
    seen_categories: list[str] | None = None
    seen_title_terms: list[str] | None = None

    async def fake_anchor(
        session: AsyncSession,
        anchor: AskAnchor,
        *,
        lat: float | None,
        lng: float | None,
        prior_steps: list[AskStep] | None = None,
        carried_intent: QueryIntent | None = None,
        title_terms: list[str] | None = None,
    ) -> AskResponse:
        nonlocal seen_action, seen_categories, seen_title_terms
        seen_action = anchor.action
        seen_categories = list(carried_intent.categoryKeywords) if carried_intent else None
        seen_title_terms = title_terms
        return _blank_response()

    monkeypatch.setattr(ask_service, "ask_with_anchor", fake_anchor)

    await ask_service.ask(
        db_session,
        None,
        None,
        question="거기 근처 삼겹살집",
        lat=None,
        lng=None,
        image_bytes=None,
        image_mime=None,
        context=AskContext(
            intent=QueryIntent(categoryKeywords=[prior_keyword]), focusContentId="focus-1"
        ),
    )

    assert seen_action == "food"
    assert seen_categories == ["삼겹살집", "삼겹살"]
    assert seen_title_terms == ["삼겹살"]


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("food", ["삼겹살"]),
        ("cafe", []),
        ("nearby", []),
        ("related", []),
        ("crowd", []),
    ],
)
def test_only_food_action_keeps_dish_title_terms(action: AnchorAction, expected: list[str]) -> None:
    assert ask_service._title_terms_for_action(action, ["삼겹살"]) == expected


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
    monkeypatch.setattr(food_service, "_ask_around", fake_around)

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
