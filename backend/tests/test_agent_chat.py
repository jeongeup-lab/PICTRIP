from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from fakeredis.aioredis import FakeRedis
from pydantic import BaseModel, ValidationError

from app.modules.agent import naver
from app.modules.agent.emitter import Emitter
from app.modules.agent.naver import NaverBlogPost
from app.modules.agent.schemas import (
    AgentSpotCard,
    AnchorAction,
    AnswerSegment,
    AskAnchor,
    AskResponse,
    AskStep,
    ChatRequest,
    QueryIntent,
    RefinePatch,
    Suggestion,
)
from app.modules.agent.services import chat as chat_service

PIECES = [
    "부산 계곡이라면 여기예요.\n",
    "- **계곡-v1**[1] 물이 맑아요.\n",
]
CLIENT_REQUEST_ID = "request-1"


def _result(answer: list[AnswerSegment] | None = None) -> AskResponse:
    return AskResponse(
        steps=[
            AskStep(tool="intent", label="질문에서 지역·조건 추출", badge="AI 해석"),
            AskStep(tool="category_search", label="부산 관광지 조회", badge="1곳"),
        ],
        answer=answer or [],
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


def test_blog_probe_strips_brackets_and_wide_region() -> None:
    result = _result()
    result.spots[0].title = "[백년가게]대일정"
    result.spots[0].regionLabel = "전북특별자치도 정읍시"

    probes = chat_service._blog_probes(result, message="정읍 맛집 추천해줘")

    assert probes[0].query == "정읍시 대일정"
    assert probes[0].terms == ("대일정",)
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

    assert chat_service._post_matches(related, ("대일정",)) is True
    assert chat_service._post_matches(unrelated, ("대일정",)) is False


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


@pytest.mark.parametrize("client_request_id", ["", "x" * 129])
def test_chat_request_requires_bounded_non_empty_client_request_id(client_request_id: str) -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message="부산 계곡", clientRequestId=client_request_id)


def test_chat_request_generates_client_request_id_when_omitted() -> None:
    request = ChatRequest(message="부산 계곡")

    assert 1 <= len(request.clientRequestId) <= 128


def test_region_alone_does_not_keep_an_off_topic_post() -> None:
    off_topic = NaverBlogPost(
        title="노인일자리 신청방법",
        link="https://blog.naver.com/c",
        description="정읍 지역 접수처 안내",
        postdate="20260801",
    )

    assert chat_service._post_matches(off_topic, ("정읍", "맛집")) is False
    assert chat_service._post_matches(off_topic, ("정읍", "일자리")) is True


def _talk(task: str, sentence: str) -> AskResponse:
    return AskResponse(
        steps=[],
        answer=[AnswerSegment(text=sentence)],
        spots=[],
        totalCount=0,
        intent=QueryIntent(task=task),  # type: ignore[arg-type]
        refinements=[],
    )


def test_history_over_the_cap_is_clipped_not_rejected() -> None:
    """20장을 돌려준 직전 턴이 다음 턴을 통째로 400 으로 죽이면 안 된다."""
    payload = ChatRequest.model_validate(
        {
            "message": "다른 곳도 알려줘",
            "history": [
                {"role": "user", "text": "제주 자연 풍경 좋은 곳"},
                {
                    "role": "assistant",
                    "text": "가",
                    "spotIds": [str(i) for i in range(20)],
                },
            ],
        }
    )

    assert len(payload.history[-1].spotIds) == 8
    assert payload.history[-1].spotIds == [str(i) for i in range(8)]


def test_history_longer_than_the_window_keeps_the_latest_turns() -> None:
    payload = ChatRequest.model_validate(
        {
            "message": "그럼 근처 카페는?",
            "history": [{"role": "user", "text": f"질문{i}"} for i in range(12)],
        }
    )

    assert len(payload.history) == 8
    assert payload.history[0].text == "질문4"
    assert payload.history[-1].text == "질문11"


def test_overlong_history_text_is_clipped() -> None:
    payload = ChatRequest.model_validate({"history": [{"role": "assistant", "text": "가" * 900}]})

    assert len(payload.history[0].text) == 500


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["food", "cafe", "nearby", "crowd", "related"])
async def test_chat_hands_the_anchor_to_the_search(
    action: AnchorAction, monkeypatch: pytest.MonkeyPatch
) -> None:
    """카드에서 누른 앵커는 채팅 스트림도 그대로 실어야 한다 — 안 실으면 일반 검색이 된다."""
    seen: dict[str, Any] = {}

    async def _fake_run(*_args: Any, **kwargs: Any) -> AskResponse:
        seen.update(kwargs)
        return _result()

    monkeypatch.setattr(chat_service.search, "run", _fake_run)
    anchor = AskAnchor(contentId="a1", action=action)

    await chat_service._search(
        None,
        None,
        None,
        payload=ChatRequest(anchor=anchor),
        image_bytes=None,
        image_mime=None,
        emitter=Emitter(),
    )

    assert seen["anchor"] == anchor
