from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from pydantic import ValidationError

from app.config import Settings
from app.modules.agent import llm
from app.modules.agent.schemas import AnswerSegment, AskResponse, AskStep, ChatRequest, QueryIntent
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import chat as chat_service
from app.modules.agent.services import intent as intent_service


@pytest_asyncio.fixture(autouse=True)
async def _close_llm_clients() -> AsyncIterator[None]:
    await llm.close_client()
    yield
    await llm.close_client()


def test_gemini_remains_the_default_writer_provider() -> None:
    settings = Settings()

    assert settings.LLM_PROVIDER == "gemini"


def test_local_codex_writer_uses_the_planned_endpoint_and_model(monkeypatch) -> None:
    configured = Settings(
        ENVIRONMENT="local",
        LLM_PROVIDER="codex",
    )
    monkeypatch.setattr(llm, "settings", configured)

    client = llm.get_writer_client()

    assert isinstance(client, llm.CodexClient)
    assert str(client._client.base_url) == "http://127.0.0.1:18787/v1/"
    assert client._model == "gpt-5.4-mini"


@pytest.mark.parametrize(
    "overrides",
    [
        {"ENVIRONMENT": "production", "LLM_PROVIDER": "codex"},
        {"ENVIRONMENT": "local", "LLM_PROVIDER": "codex", "CODEX_BASE_URL": "http://localhost"},
        {"ENVIRONMENT": "local", "LLM_PROVIDER": "codex", "CODEX_MODEL": "gpt-5.4"},
    ],
)
def test_settings_rejects_invalid_codex_writer_configuration(overrides: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        Settings(**overrides)


@pytest.mark.anyio
async def test_codex_client_ignores_proxy_environment() -> None:
    client = llm.CodexClient(
        base_url="http://127.0.0.1:18787/v1",
        model="gpt-5.4-mini",
    )

    try:
        assert client._client._trust_env is False
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_codex_stream_posts_openai_messages_and_yields_first_choice_content() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
                b'data: {"choices":[{"delta":{"role":"assistant","content":"one"}},'
                b'{"delta":{"content":"ignored"}}]}\n\n'
                b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
                b'data: {"choices":[{"delta":{"content":"two"}}]}\n\n'
                b"data: [DONE]\n\n"
            ),
            request=request,
        )

    transport = httpx.MockTransport(handler)
    client = llm.CodexClient(
        base_url="http://127.0.0.1:18787/v1",
        model="gpt-5.4-mini",
        transport=transport,
    )

    try:
        chunks = [chunk async for chunk in client.stream_text(system="system", user_text="user")]
    finally:
        await client.aclose()

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert request.url == "http://127.0.0.1:18787/v1/chat/completions"
    assert json.loads(request.content) == {
        "model": "gpt-5.4-mini",
        "stream": True,
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ],
    }
    assert chunks == ["one", "two"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "line",
    [
        "data: not-json",
        'data: {"error":{"message":"proxy refused"}}',
        'data: {"id":"chatcmpl-1"}',
    ],
)
async def test_codex_stream_rejects_invalid_sse_payloads(line: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=f"{line}\n\n".encode(),
            request=request,
        )

    client = llm.CodexClient(
        base_url="http://127.0.0.1:18787/v1",
        model="gpt-5.4-mini",
        transport=httpx.MockTransport(handler),
    )

    try:
        with pytest.raises(llm.CodexStreamProtocolError):
            _ = [chunk async for chunk in client.stream_text(system="system", user_text="user")]
    finally:
        await client.aclose()


class _FakeIntentClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate_json(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {}

    async def stream_text(self, *, system: str, user_text: str) -> AsyncIterator[str]:
        yield "legacy path\n"


class _FakeWriterClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def stream_text(self, *, system: str, user_text: str) -> AsyncIterator[str]:
        self.calls.append({"system": system, "user_text": user_text})
        yield "answer\n"


@pytest.mark.anyio
async def test_chat_uses_writer_client_while_intent_extraction_keeps_get_client(
    monkeypatch,
) -> None:
    writer_client = _FakeWriterClient()
    intent_client = _FakeIntentClient()

    async def fake_ask(*args: Any, **kwargs: Any):
        return AskResponse(
            steps=[],
            answer=[],
            spots=[],
            totalCount=0,
            intent=QueryIntent(),
            refinements=[],
        )

    monkeypatch.setattr(ask_service, "ask", fake_ask)
    monkeypatch.setattr(llm, "get_client", lambda: intent_client)
    monkeypatch.setattr(llm, "get_writer_client", lambda: writer_client, raising=False)

    events = [
        event
        async for event in chat_service.events(
            None,
            None,
            None,
            payload=ChatRequest(message="question", clientRequestId="request-1"),
            image_bytes=None,
            image_mime=None,
        )
    ]

    assert writer_client.calls
    assert [name for name, _ in events if name == "delta"] == ["delta"]


@pytest.mark.anyio
async def test_local_codex_writer_runs_after_intent_fallback_badge(monkeypatch) -> None:
    configured = Settings(
        ENVIRONMENT="local",
        LLM_PROVIDER="codex",
    )
    writer_client = _FakeWriterClient()

    async def fake_ask(*args: Any, **kwargs: Any):
        return AskResponse(
            steps=[AskStep(tool="intent", label="intent", badge=ask_service.INTENT_FALLBACK_BADGE)],
            answer=[AnswerSegment(text="deterministic fallback")],
            spots=[],
            totalCount=0,
            intent=QueryIntent(),
            refinements=[],
        )

    monkeypatch.setattr(llm, "settings", configured)
    monkeypatch.setattr(ask_service, "ask", fake_ask)
    monkeypatch.setattr(llm, "get_writer_client", lambda: writer_client, raising=False)

    events = [
        event
        async for event in chat_service.events(
            None,
            None,
            None,
            payload=ChatRequest(message="question", clientRequestId="request-1"),
            image_bytes=None,
            image_mime=None,
        )
    ]

    assert writer_client.calls
    assert [event.text for name, event in events if name == "delta"] == ["answer\n"]


@pytest.mark.anyio
async def test_gemini_writer_skips_after_intent_fallback_badge(monkeypatch) -> None:
    configured = Settings(LLM_PROVIDER="gemini")

    async def fake_ask(*args: Any, **kwargs: Any):
        return AskResponse(
            steps=[AskStep(tool="intent", label="intent", badge=ask_service.INTENT_FALLBACK_BADGE)],
            answer=[AnswerSegment(text="deterministic fallback")],
            spots=[],
            totalCount=0,
            intent=QueryIntent(),
            refinements=[],
        )

    def writer_must_not_run() -> _FakeWriterClient:
        raise AssertionError("Gemini writer must not run after intent fallback")

    monkeypatch.setattr(llm, "settings", configured)
    monkeypatch.setattr(ask_service, "ask", fake_ask)
    monkeypatch.setattr(llm, "get_writer_client", writer_must_not_run, raising=False)

    events = [
        event
        async for event in chat_service.events(
            None,
            None,
            None,
            payload=ChatRequest(message="question", clientRequestId="request-1"),
            image_bytes=None,
            image_mime=None,
        )
    ]

    assert [event.text for name, event in events if name == "delta"] == ["deterministic fallback"]


@pytest.mark.anyio
async def test_intent_extraction_uses_existing_gemini_client(monkeypatch) -> None:
    intent_client = _FakeIntentClient()
    monkeypatch.setattr(llm, "get_client", lambda: intent_client)

    await intent_service.extract_intent("question")

    assert len(intent_client.calls) == 1


def test_deepseek_writer_uses_the_configured_endpoint_and_model(monkeypatch) -> None:
    configured = Settings(LLM_PROVIDER="deepseek", DEEPSEEK_API_KEY="sk-live")
    monkeypatch.setattr(llm, "settings", configured)

    client = llm.get_writer_client()

    assert isinstance(client, llm.DeepSeekClient)
    assert str(client._client.base_url) == "https://api.deepseek.com/v1/"
    assert client._model == "deepseek-chat"


def test_deepseek_writer_sends_the_api_key_because_it_is_a_metered_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        llm, "settings", Settings(LLM_PROVIDER="deepseek", DEEPSEEK_API_KEY="sk-live")
    )

    client = llm.get_writer_client()

    assert client._client.headers["authorization"] == "Bearer sk-live"


@pytest.mark.parametrize(
    "overrides",
    [
        {"LLM_PROVIDER": "deepseek"},
        {"LLM_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": ""},
        {
            "LLM_PROVIDER": "deepseek",
            "DEEPSEEK_API_KEY": "sk-live",
            "DEEPSEEK_BASE_URL": "http://api.deepseek.com/v1",
        },
    ],
)
def test_settings_rejects_a_deepseek_writer_that_would_leak_or_fail(
    overrides: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        Settings(**overrides)


def test_deepseek_unlike_codex_is_allowed_outside_local_because_it_is_a_hosted_api() -> None:
    configured = Settings(
        ENVIRONMENT="production", LLM_PROVIDER="deepseek", DEEPSEEK_API_KEY="sk-live"
    )

    assert configured.LLM_PROVIDER == "deepseek"


@pytest.mark.anyio
async def test_deepseek_reasoning_deltas_are_skipped_rather_than_treated_as_answer_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                b'data: {"choices":[{"delta":{"reasoning_content":"thinking"}}]}\n\n'
                b'data: {"choices":[{"delta":{"content":"\xeb\xb0\x94\xeb\x8b\xa4"}}]}\n\n'
                b"data: [DONE]\n\n"
            ),
            request=request,
        )

    client = llm.DeepSeekClient(
        base_url="https://api.deepseek.com/v1",
        model="deepseek-v4-flash",
        api_key="sk-live",
        transport=httpx.MockTransport(handler),
    )

    try:
        pieces = [piece async for piece in client.stream_text(system="s", user_text="u")]
    finally:
        await client.aclose()

    assert pieces == ["바다"]


@pytest.mark.anyio
async def test_a_deepseek_writer_leaves_the_gemini_rescue_path_switched_off(monkeypatch) -> None:
    monkeypatch.setattr(
        llm, "settings", Settings(LLM_PROVIDER="deepseek", DEEPSEEK_API_KEY="sk-live")
    )

    assert llm.writer_depends_on_gemini() is False
