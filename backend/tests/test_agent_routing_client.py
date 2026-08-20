from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.modules.agent.llm import GeminiClient, OpenAIChatClient
from app.modules.agent.routing import Decision, ToolCall, Turn
from app.web.errors import RateLimited

pytestmark = pytest.mark.asyncio

TOOLS: list[dict[str, Any]] = [
    {
        "name": "category_search",
        "description": "지역·카테고리로 찾는다",
        "parameters": {"type": "object", "properties": {"regions": {"type": "array"}}},
    }
]


def _gemini(handler: object) -> GeminiClient:
    client = GeminiClient()
    client._client = httpx.AsyncClient(  # type: ignore[assignment]
        base_url="https://gemini.test", transport=httpx.MockTransport(handler)
    )
    return client


def _openai(handler: object) -> OpenAIChatClient:
    return OpenAIChatClient(
        base_url="https://deepseek.test",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )


async def test_gemini_reads_a_function_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "category_search",
                                        "args": {"regions": ["통영"]},
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    client = _gemini(handler)
    try:
        decision = await client.decide(
            system="라우터", turns=[Turn(role="user", text="통영 카페")], tools=TOOLS
        )
    finally:
        await client.aclose()

    assert decision == Decision(
        calls=[ToolCall(name="category_search", args={"regions": ["통영"]})], text=None
    )
    assert decision.done is False


async def test_openai_reads_a_tool_call_with_string_arguments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "abc",
                                    "type": "function",
                                    "function": {
                                        "name": "category_search",
                                        "arguments": '{"regions": ["부산"]}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    client = _openai(handler)
    try:
        decision = await client.decide(
            system="라우터", turns=[Turn(role="user", text="부산 카페")], tools=TOOLS
        )
    finally:
        await client.aclose()

    assert decision.calls == [ToolCall(name="category_search", args={"regions": ["부산"]})]


async def test_no_tool_call_means_the_loop_stops() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "더 찾을 게 없어요."}}]}
        )

    client = _openai(handler)
    try:
        decision = await client.decide(system="라우터", turns=[], tools=TOOLS)
    finally:
        await client.aclose()

    assert decision.done is True
    assert decision.text == "더 찾을 게 없어요."


async def test_malformed_arguments_do_not_kill_the_turn() -> None:
    """모델이 깨진 JSON 을 보내도 빈 인자로 부르고 도구가 관찰을 돌려준다."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "category_search",
                                        "arguments": "{not json",
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    client = _openai(handler)
    try:
        decision = await client.decide(system="라우터", turns=[], tools=TOOLS)
    finally:
        await client.aclose()

    assert decision.calls == [ToolCall(name="category_search", args={})]


async def test_quota_429_surfaces_as_rate_limited() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="quota")

    client = _openai(handler)
    try:
        with pytest.raises(RateLimited):
            await client.decide(system="라우터", turns=[], tools=TOOLS)
    finally:
        await client.aclose()


async def test_observations_are_paired_with_their_calls_for_openai() -> None:
    """응답 메시지가 tool_call_id 로 짝지어지지 않으면 프로바이더가 400 을 낸다."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "끝"}}]})

    client = _openai(handler)
    try:
        await client.decide(
            system="라우터",
            turns=[
                Turn(role="user", text="통영 카페"),
                Turn(role="call", calls=[ToolCall(name="category_search", args={})]),
                Turn(role="observation", text="11곳", tool_name="category_search"),
            ],
            tools=TOOLS,
        )
    finally:
        await client.aclose()

    messages = captured["messages"]
    assistant = next(m for m in messages if m["role"] == "assistant")
    tool = next(m for m in messages if m["role"] == "tool")
    assert tool["tool_call_id"] == assistant["tool_calls"][0]["id"]


async def test_gemini_sends_function_responses_not_plain_text() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "끝"}]}}]})

    client = _gemini(handler)
    try:
        await client.decide(
            system="라우터",
            turns=[
                Turn(role="user", text="통영 카페"),
                Turn(role="call", calls=[ToolCall(name="category_search", args={})]),
                Turn(role="observation", text="11곳", tool_name="category_search"),
            ],
            tools=TOOLS,
        )
    finally:
        await client.aclose()

    roles = [content["role"] for content in captured["contents"]]
    assert roles == ["user", "model", "user"]
    assert captured["contents"][2]["parts"][0]["functionResponse"]["name"] == "category_search"
    assert captured["tools"] == [{"functionDeclarations": TOOLS}]
