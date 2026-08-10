from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fakeredis.aioredis import FakeRedis
from pydantic import BaseModel

from app.core.db import get_db
from app.core.redis import get_redis
from app.kto.client import get_kto
from app.main import app
from app.modules.agent import llm, naver
from app.modules.agent.errors import AgentNoResults, AgentWriterUnavailable
from app.modules.agent.naver import NaverBlogPost
from app.modules.agent.schemas import (
    AgentSpotCard,
    AskResponse,
    AskStep,
    ChatRequest,
    QueryIntent,
    RefinePatch,
    Suggestion,
)
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import chat as chat_service

PIECES = [
    "부산 계곡이라면 여기예요.\n",
    "[[cards]]\n",
    "- **계곡-v1** 물이 맑아요.\n",
    "[[suggest: 더 한적한 곳 | 근처 맛집]]",
]


def _result() -> AskResponse:
    return AskResponse(
        steps=[
            AskStep(tool="intent", label="질문에서 지역·조건 추출", badge="Gemini"),
            AskStep(tool="category_search", label="부산 관광지 조회", badge="1곳"),
        ],
        answer=[],
        spots=[
            AgentSpotCard(
                contentId="v1",
                title="계곡-v1",
                regionLabel="부산광역시 사하구",
                tag="한산",
                hasCrowd=True,
            )
        ],
        totalCount=1,
        intent=QueryIntent(categoryKeywords=["계곡"], regionHints=["부산"]),
        refinements=[Suggestion(label="가까운 순으로", patch=RefinePatch(nearMe=True))],
        tagBasis="혼잡도 예측 기준",
    )


class _FakeGemini:
    def __init__(self, pieces: list[str], *, error: Exception | None = None) -> None:
        self._pieces = pieces
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def stream_text(
        self, *, system: str, user_text: str, temperature: float = 0.4
    ) -> AsyncIterator[str]:
        self.calls.append({"system": system, "user_text": user_text})
        for piece in self._pieces:
            yield piece
        if self._error is not None:
            raise self._error


async def _fake_blog(
    client: httpx.AsyncClient, query: str, *, display: int = 5
) -> list[NaverBlogPost]:
    return [
        NaverBlogPost(
            title=f"{query} 후기",
            link=f"https://blog.naver.com/x/{len(query)}",
            description="블로그 요약",
            postdate="20260801",
        )
    ]


def _wire(monkeypatch, *, gemini: _FakeGemini) -> None:
    async def fake_ask(session, redis, kto, **kwargs) -> AskResponse:
        return _result()

    monkeypatch.setattr(ask_service, "ask", fake_ask)
    monkeypatch.setattr(naver, "is_configured", lambda: True)
    monkeypatch.setattr(naver, "search_blog", _fake_blog)
    monkeypatch.setattr(llm, "get_client", lambda: gemini)


async def _collect(payload: ChatRequest) -> list[tuple[str, BaseModel]]:
    redis = FakeRedis(decode_responses=True)
    try:
        return [
            event
            async for event in chat_service.events(
                None, redis, None, payload=payload, image_bytes=None, image_mime=None
            )
        ]
    finally:
        await redis.aclose()


async def test_chat_events_follow_the_step_delta_cards_sources_suggestions_done_order(
    monkeypatch,
) -> None:
    _wire(monkeypatch, gemini=_FakeGemini(PIECES))

    events = await _collect(ChatRequest(message="부산 계곡"))

    names = [name for name, _ in events]
    assert names == [
        "step",
        "step",
        "step",
        "step",
        "delta",
        "cards",
        "delta",
        "sources",
        "suggestions",
        "done",
    ]
    steps = [event.model_dump() for name, event in events if name == "step"]
    assert [step["status"] for step in steps] == ["run", "done", "run", "done"]
    assert steps[0]["index"] == steps[1]["index"] == 0
    assert steps[1]["badge"] == "Gemini"
    deltas = "".join(event.model_dump()["text"] for name, event in events if name == "delta")
    assert "[[" not in deltas
    done = events[-1][1].model_dump()
    assert done["answerText"] == "부산 계곡이라면 여기예요.\n- **계곡-v1** 물이 맑아요."
    assert done["suggestions"] == ["더 한적한 곳", "근처 맛집"]
    assert done["totalCount"] == 1
    assert [spot["contentId"] for spot in done["spots"]] == ["v1"]


async def test_chat_cards_event_carries_the_ask_spots_and_tag_basis(monkeypatch) -> None:
    _wire(monkeypatch, gemini=_FakeGemini(PIECES))

    events = await _collect(ChatRequest(message="부산 계곡"))

    cards = next(event.model_dump() for name, event in events if name == "cards")
    assert [spot["contentId"] for spot in cards["spots"]] == ["v1"]
    assert cards["tagBasis"] == "혼잡도 예측 기준"


async def test_chat_sources_hold_the_grounding_blogs_plus_the_fixed_kto_row(monkeypatch) -> None:
    _wire(monkeypatch, gemini=_FakeGemini(PIECES))

    events = await _collect(ChatRequest(message="부산 계곡"))

    sources = next(event.model_dump() for name, event in events if name == "sources")
    kinds = [item["kind"] for item in sources["items"]]
    assert "naver_blog" in kinds
    assert kinds[-1] == "kto"
    blog = next(item for item in sources["items"] if item["kind"] == "naver_blog")
    assert blog["url"].startswith("https://blog.naver.com/")
    assert blog["date"] == "20260801"


async def test_chat_falls_back_to_refinement_labels_when_the_writer_skips_suggestions(
    monkeypatch,
) -> None:
    _wire(monkeypatch, gemini=_FakeGemini(["결론이에요.\n", "\n", "팁이에요."]))

    events = await _collect(ChatRequest(message="부산 계곡"))

    suggestions = next(event.model_dump() for name, event in events if name == "suggestions")
    assert suggestions["items"] == ["가까운 순으로"]
    names = [name for name, _ in events]
    assert names.index("cards") < names.index("sources")


async def test_chat_turns_an_ask_error_into_a_delta_and_a_clean_done(monkeypatch) -> None:
    async def failing_ask(session, redis, kto, **kwargs) -> AskResponse:
        raise AgentNoResults()

    def forbidden_client() -> Any:
        raise AssertionError("writer must not run when ask fails")

    monkeypatch.setattr(ask_service, "ask", failing_ask)
    monkeypatch.setattr(llm, "get_client", forbidden_client)

    events = await _collect(ChatRequest(message="아무거나"))

    assert [name for name, _ in events] == ["delta", "done"]
    assert events[0][1].model_dump()["text"] == AgentNoResults.message
    done = events[-1][1].model_dump()
    assert done["answerText"] == AgentNoResults.message
    assert done["spots"] == []
    assert done["suggestions"] == []


async def test_a_writer_failure_ends_the_stream_with_an_error_event(monkeypatch) -> None:
    _wire(
        monkeypatch,
        gemini=_FakeGemini(["결론이에요.\n"], error=httpx.ReadError("boom")),
    )

    events = await _collect(ChatRequest(message="부산 계곡"))

    names = [name for name, _ in events]
    assert names[-1] == "error"
    assert "done" not in names
    assert "sources" not in names
    error = events[-1][1].model_dump()
    assert error["code"] == AgentWriterUnavailable.code
    assert error["message"] == AgentWriterUnavailable.message


def _override() -> None:
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_redis] = lambda: FakeRedis(decode_responses=True)
    app.dependency_overrides[get_kto] = lambda: None


def _parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    parsed: list[tuple[str, dict[str, Any]]] = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        lines = block.split("\n")
        assert lines[0].startswith("event: ")
        assert lines[1].startswith("data: ")
        parsed.append((lines[0][len("event: ") :], json.loads(lines[1][len("data: ") :])))
    return parsed


async def test_chat_route_streams_sse_instead_of_a_jsend_envelope(client, monkeypatch) -> None:
    _wire(monkeypatch, gemini=_FakeGemini(PIECES))
    _override()
    try:
        res = await client.post("/v1/agent/chat", json={"message": "부산 계곡"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert res.headers["cache-control"] == "no-cache"
    assert res.headers["x-accel-buffering"] == "no"
    assert res.text.startswith("event: ")
    events = _parse_sse(res.text)
    assert events[-1][0] == "done"
    done = events[-1][1]
    assert set(done) >= {"answerText", "spots", "sources", "suggestions", "intent", "totalCount"}
    assert "data" not in done
    assert "meta" not in done


async def test_chat_route_rejects_an_invalid_payload_with_jsend_before_streaming(client) -> None:
    _override()
    try:
        res = await client.post("/v1/agent/chat", json={"message": "가" * 501})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"


def test_blog_probe_strips_brackets_and_wide_region() -> None:
    result = _result()
    result.spots[0].title = "[백년가게]대일정"
    result.spots[0].regionLabel = "전북특별자치도 정읍시"

    probes = chat_service._blog_probes(result, message="정읍 맛집 추천해줘")

    assert probes[0].query == "정읍시 대일정"
    assert probes[0].terms == ("대일정", "정읍시")
    assert probes[-1].query == "정읍 맛집"


def test_unrelated_blog_posts_are_dropped() -> None:
    related = NaverBlogPost(
        title="정읍시 대일정 다녀왔어요",
        link="https://blog.naver.com/a",
        description="정갈한 한식",
        postdate="20260801",
    )
    unrelated = NaverBlogPost(
        title="노인일자리 신청방법 총정리",
        link="https://blog.naver.com/b",
        description="고용노동부 안내",
        postdate="20260801",
    )

    assert chat_service._post_matches(related, ("대일정", "정읍시")) is True
    assert chat_service._post_matches(unrelated, ("대일정", "정읍시")) is False


async def test_grounding_keeps_only_matching_posts(monkeypatch) -> None:
    result = _result()
    result.spots[0].title = "대일정"
    result.spots[0].regionLabel = "전북특별자치도 정읍시"

    async def mixed_blog(
        client: httpx.AsyncClient, query: str, *, display: int = 5
    ) -> list[NaverBlogPost]:
        return [
            NaverBlogPost(
                title="정읍시 대일정 밥상",
                link="https://blog.naver.com/keep",
                description="한식",
                postdate="20260801",
            ),
            NaverBlogPost(
                title="강소기업 명단 정리",
                link="https://blog.naver.com/drop",
                description="채용 공고",
                postdate="20240502",
            ),
        ]

    monkeypatch.setattr(naver, "is_configured", lambda: True)
    monkeypatch.setattr(naver, "search_blog", mixed_blog)

    posts = await chat_service._ground_with_blogs(result, message="정읍 맛집 추천해줘")

    assert [post.link for post in posts] == ["https://blog.naver.com/keep"]
