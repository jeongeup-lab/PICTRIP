from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol, assert_never

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.core.logging import get_logger
from app.modules.agent.errors import AgentIntentUnavailable
from app.modules.agent.routing import Decision, ToolCall, Turn
from app.web.errors import RateLimited

logger = get_logger(__name__)


MAX_ERROR_BODY_CHARS = 500

STRUCTURED_TIMEOUT_SECONDS = 4.0
STRUCTURED_MAX_OUTPUT_TOKENS = 2048
STRUCTURED_ATTEMPTS = 2
ROUTING_TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True, slots=True)
class CodexStreamProtocolError(Exception):
    reason: str

    def __str__(self) -> str:
        return f"Codex stream protocol error: {self.reason}"


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError))


def _failure_detail(exc: BaseException) -> str | None:
    if not isinstance(exc, httpx.HTTPStatusError):
        return None
    return exc.response.text[:MAX_ERROR_BODY_CHARS] or None


def _loads(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _gemini_contents(turns: list[Turn]) -> list[dict[str, Any]]:
    """한 모델 턴의 병렬 호출 응답은 하나의 user content 로 묶는다 — 쪼개면 400 이 난다."""
    contents: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []

    def flush() -> None:
        if pending:
            contents.append({"role": "user", "parts": list(pending)})
            pending.clear()

    for turn in turns:
        if turn.role == "observation":
            pending.append(
                {
                    "functionResponse": {
                        "name": turn.tool_name or "",
                        "response": {"result": turn.text},
                    }
                }
            )
            continue
        flush()
        if turn.role == "call":
            contents.append(
                {
                    "role": "model",
                    "parts": [
                        {"functionCall": {"name": call.name, "args": call.args}}
                        for call in turn.calls
                    ],
                }
            )
        else:
            contents.append({"role": "user", "parts": [{"text": turn.text}]})
    flush()
    return contents


def _openai_turns(turns: list[Turn]) -> list[dict[str, Any]]:
    """도구 호출마다 고유 id 를 붙인다 — OpenAI 호환은 응답을 id 로 짝짓는다."""
    messages: list[dict[str, Any]] = []
    pending: list[str] = []
    for index, turn in enumerate(turns):
        if turn.role == "user":
            messages.append({"role": "user", "content": turn.text})
        elif turn.role == "call":
            pending = [f"c{index}_{position}" for position in range(len(turn.calls))]
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": pending[position],
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.args, ensure_ascii=False),
                            },
                        }
                        for position, call in enumerate(turn.calls)
                    ],
                }
            )
        else:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": pending.pop(0) if pending else f"c{index}",
                    "content": turn.text,
                }
            )
    return messages


class GeminiClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.GEMINI_BASE_URL,
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={"x-goog-api-key": settings.GEMINI_API_KEY},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(STRUCTURED_ATTEMPTS),
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,
    )
    async def _generate(self, body: dict[str, Any], *, request_timeout: float) -> httpx.Response:
        resp = await self._client.post(
            f"/models/{settings.GEMINI_MODEL}:generateContent", json=body, timeout=request_timeout
        )
        resp.raise_for_status()
        return resp

    async def generate_json(
        self,
        *,
        system: str,
        user_text: str | None = None,
        image_bytes: bytes | None = None,
        image_mime: str | None = None,
        video_uri: str | None = None,
        response_schema: dict[str, Any],
        request_timeout: float = STRUCTURED_TIMEOUT_SECONDS,
    ) -> Any:
        parts: list[dict[str, Any]] = []
        if video_uri:
            parts.append({"fileData": {"fileUri": video_uri}})
        if image_bytes:
            parts.append(
                {
                    "inlineData": {
                        "mimeType": image_mime or "image/jpeg",
                        "data": base64.b64encode(image_bytes).decode(),
                    }
                }
            )
        if user_text:
            parts.append({"text": user_text})
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": response_schema,
                "temperature": 0.0,
                "maxOutputTokens": STRUCTURED_MAX_OUTPUT_TOKENS,
            },
        }
        try:
            resp = await self._generate(body, request_timeout=request_timeout)
            payload = resp.json()
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            logger.warning(
                "agent.llm.failed",
                error_type=type(exc).__name__,
                status=(
                    exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                ),
                detail=_failure_detail(exc),
            )
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                raise RateLimited() from exc
            raise AgentIntentUnavailable() from exc

    async def decide(
        self,
        *,
        system: str,
        turns: list[Turn],
        tools: list[dict[str, Any]],
        request_timeout: float = ROUTING_TIMEOUT_SECONDS,
    ) -> Decision:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": _gemini_contents(turns),
            "tools": [{"functionDeclarations": tools}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": STRUCTURED_MAX_OUTPUT_TOKENS,
            },
        }
        try:
            resp = await self._generate(body, request_timeout=request_timeout)
            parts = resp.json()["candidates"][0]["content"].get("parts", [])
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("agent.route.failed", error_type=type(exc).__name__)
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                raise RateLimited() from exc
            raise AgentIntentUnavailable() from exc
        calls = [
            ToolCall(name=call["name"], args=dict(call.get("args") or {}))
            for part in parts
            if isinstance(call := part.get("functionCall"), dict) and call.get("name")
        ]
        said = "".join(part["text"] for part in parts if isinstance(part.get("text"), str))
        return Decision(calls=calls, text=said or None)

    async def stream_text(
        self, *, system: str, user_text: str, temperature: float = 0.4
    ) -> AsyncIterator[str]:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {"temperature": temperature},
        }
        response = await self._open_stream(body)
        try:
            async for line in response.aiter_lines():
                piece = _stream_piece(line)
                if piece:
                    yield piece
        finally:
            await response.aclose()

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,
    )
    async def _open_stream(self, body: dict[str, Any]) -> httpx.Response:
        request = self._client.build_request(
            "POST",
            f"/models/{settings.GEMINI_MODEL}:streamGenerateContent",
            params={"alt": "sse"},
            json=body,
        )
        response = await self._client.send(request, stream=True)
        if response.status_code >= 400:
            await response.aread()
            await response.aclose()
            response.raise_for_status()
        return response


class WriterClient(Protocol):
    async def aclose(self) -> None: ...

    def stream_text(self, *, system: str, user_text: str) -> AsyncIterator[str]: ...


_JSON_INSTRUCTION = """\

너는 JSON 만 출력한다. 설명·머리말·코드펜스를 붙이지 않는다.
아래 JSON Schema 를 정확히 따른다. 스키마에 없는 키를 만들지 않는다.

{schema}
"""


class OpenAIChatClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(60.0, connect=10.0),
            transport=transport,
            trust_env=False,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else None,
        )
        self._model = model

    async def aclose(self) -> None:
        await self._client.aclose()

    async def generate_json(
        self,
        *,
        system: str,
        user_text: str | None = None,
        image_bytes: bytes | None = None,
        image_mime: str | None = None,
        video_uri: str | None = None,
        response_schema: dict[str, Any],
        request_timeout: float = STRUCTURED_TIMEOUT_SECONDS,
    ) -> Any:
        if image_bytes or video_uri:
            raise AgentIntentUnavailable()
        instructed = system + _JSON_INSTRUCTION.format(
            schema=json.dumps(response_schema, ensure_ascii=False)
        )
        body = {
            "model": self._model,
            "temperature": 0.0,
            "max_tokens": STRUCTURED_MAX_OUTPUT_TOKENS,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": instructed},
                {"role": "user", "content": user_text or ""},
            ],
        }
        try:
            resp = await self._post_json(body, request_timeout=request_timeout)
            text = resp.json()["choices"][0]["message"]["content"]
            return json.loads(text)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            logger.warning(
                "agent.llm.failed",
                error_type=type(exc).__name__,
                status=(
                    exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                ),
                detail=_failure_detail(exc),
            )
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                raise RateLimited() from exc
            raise AgentIntentUnavailable() from exc

    async def decide(
        self,
        *,
        system: str,
        turns: list[Turn],
        tools: list[dict[str, Any]],
        request_timeout: float = ROUTING_TIMEOUT_SECONDS,
    ) -> Decision:
        body = {
            "model": self._model,
            "temperature": 0.0,
            "max_tokens": STRUCTURED_MAX_OUTPUT_TOKENS,
            "messages": [{"role": "system", "content": system}, *_openai_turns(turns)],
            "tools": [{"type": "function", "function": tool} for tool in tools],
        }
        try:
            resp = await self._post_json(body, request_timeout=request_timeout)
            message = resp.json()["choices"][0]["message"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("agent.route.failed", error_type=type(exc).__name__)
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                raise RateLimited() from exc
            raise AgentIntentUnavailable() from exc
        calls: list[ToolCall] = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            if not function.get("name"):
                continue
            calls.append(ToolCall(name=function["name"], args=_loads(function.get("arguments"))))
        said = message.get("content")
        return Decision(calls=calls, text=said if isinstance(said, str) and said else None)

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(STRUCTURED_ATTEMPTS),
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,
    )
    async def _post_json(self, body: dict[str, Any], *, request_timeout: float) -> httpx.Response:
        resp = await self._client.post("/chat/completions", json=body, timeout=request_timeout)
        resp.raise_for_status()
        return resp

    async def stream_text(self, *, system: str, user_text: str) -> AsyncIterator[str]:
        request = self._client.build_request(
            "POST",
            "/chat/completions",
            json={
                "model": self._model,
                "stream": True,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_text},
                ],
            },
        )
        response = await self._client.send(request, stream=True)
        try:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data:") and line[len("data:") :].strip() == "[DONE]":
                    return
                piece = _codex_stream_piece(line)
                if piece:
                    yield piece
        finally:
            await response.aclose()


class CodexClient(OpenAIChatClient):
    pass


class DeepSeekClient(OpenAIChatClient):
    pass


def _stream_piece(line: str) -> str | None:
    if not line.startswith("data:"):
        return None
    payload = line[len("data:") :].strip()
    if not payload or payload == "[DONE]":
        return None
    try:
        parts = json.loads(payload)["candidates"][0]["content"]["parts"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        return None
    if not isinstance(parts, list):
        return None
    texts = [part["text"] for part in parts if isinstance(part, dict) and "text" in part]
    return "".join(texts) or None


def _codex_stream_piece(line: str) -> str | None:
    if not line.startswith("data:"):
        return None
    payload = line[len("data:") :].strip()
    if not payload:
        raise CodexStreamProtocolError(reason="empty data payload")
    try:
        event = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise CodexStreamProtocolError(reason="malformed JSON payload") from exc
    if not isinstance(event, dict):
        raise CodexStreamProtocolError(reason="payload must be an object")
    if "error" in event:
        raise CodexStreamProtocolError(reason="proxy returned an error payload")
    choices = event.get("choices")
    if not isinstance(choices, list) or not choices:
        raise CodexStreamProtocolError(reason="payload is missing choices")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise CodexStreamProtocolError(reason="choice must be an object")
    delta = choice.get("delta")
    if delta is None and choice.get("finish_reason") is not None:
        return None
    if not isinstance(delta, dict):
        raise CodexStreamProtocolError(reason="choice is missing delta")
    content = delta.get("content")
    if content is None:
        return None
    if not isinstance(content, str):
        raise CodexStreamProtocolError(reason="delta content must be a string")
    return content or None


_client: GeminiClient | None = None
_writer_client: WriterClient | None = None


def get_client() -> GeminiClient:
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client


def get_writer_client() -> WriterClient:
    global _writer_client
    match settings.LLM_PROVIDER:
        case "gemini":
            if isinstance(_writer_client, GeminiClient):
                return _writer_client
            _writer_client = get_client()
            return _writer_client
        case "codex":
            if isinstance(_writer_client, CodexClient):
                return _writer_client
            _writer_client = CodexClient(
                base_url=settings.CODEX_BASE_URL,
                model=settings.CODEX_MODEL,
            )
            return _writer_client
        case "deepseek":
            if isinstance(_writer_client, DeepSeekClient):
                return _writer_client
            _writer_client = DeepSeekClient(
                base_url=settings.DEEPSEEK_BASE_URL,
                model=settings.DEEPSEEK_MODEL,
                api_key=settings.DEEPSEEK_API_KEY,
            )
            return _writer_client
        case unreachable:
            assert_never(unreachable)


class StructuredClient(Protocol):
    async def generate_json(
        self,
        *,
        system: str,
        user_text: str | None = ...,
        image_bytes: bytes | None = ...,
        image_mime: str | None = ...,
        video_uri: str | None = ...,
        response_schema: dict[str, Any],
        request_timeout: float = ...,
    ) -> Any: ...


class RoutingClient(Protocol):
    async def decide(
        self,
        *,
        system: str,
        turns: list[Turn],
        tools: list[dict[str, Any]],
        request_timeout: float = ...,
    ) -> Decision: ...


def get_routing_client() -> RoutingClient:
    """구조화 출력과 같은 프로바이더를 쓴다 — 라우팅도 결정적 저온 호출이다."""
    if settings.LLM_PROVIDER == "gemini":
        return get_client()
    client = get_writer_client()
    if not isinstance(client, OpenAIChatClient):
        raise AgentIntentUnavailable()
    return client


def routing_depends_on_gemini() -> bool:
    return settings.LLM_PROVIDER == "gemini"


def get_structured_client() -> StructuredClient:
    if settings.LLM_PROVIDER == "gemini":
        return get_client()
    client = get_writer_client()
    if not isinstance(client, OpenAIChatClient):
        raise AgentIntentUnavailable()
    return client


def writer_depends_on_gemini() -> bool:
    return settings.LLM_PROVIDER == "gemini"


def structured_depends_on_gemini() -> bool:
    return settings.LLM_PROVIDER == "gemini"


async def close_client() -> None:
    global _client, _writer_client
    if _writer_client is _client:
        if _client is not None:
            await _client.aclose()
    else:
        if _client is not None:
            await _client.aclose()
        if _writer_client is not None:
            await _writer_client.aclose()
    _writer_client = None
    _client = None
