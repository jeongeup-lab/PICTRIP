from __future__ import annotations

import json
from time import monotonic
from typing import Any, Protocol

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
from app.web.errors import RateLimited

logger = get_logger(__name__)

TRIP_SECONDS = 60.0
REQUEST_TIMEOUT = httpx.Timeout(15.0, connect=5.0)

_GEMINI_TYPES = {
    "object": "OBJECT",
    "array": "ARRAY",
    "string": "STRING",
    "boolean": "BOOLEAN",
    "integer": "INTEGER",
    "number": "NUMBER",
}


class ProviderError(Exception):
    def __init__(self, provider: str, *, transient: bool, rate_limited: bool, detail: str) -> None:
        super().__init__(f"{provider}: {detail}")
        self.provider = provider
        self.transient = transient
        self.rate_limited = rate_limited


class JsonLlm(Protocol):
    name: str

    async def generate_json(
        self, *, system: str, user_text: str, response_schema: dict[str, Any]
    ) -> Any: ...

    async def aclose(self) -> None: ...


def to_gemini_schema(node: Any) -> Any:
    if not isinstance(node, dict):
        return node
    converted: dict[str, Any] = {}
    raw_type = node.get("type")
    if isinstance(raw_type, list):
        primary = next((item for item in raw_type if item != "null"), "string")
        converted["type"] = _GEMINI_TYPES[primary]
        if "null" in raw_type:
            converted["nullable"] = True
    elif isinstance(raw_type, str):
        converted["type"] = _GEMINI_TYPES[raw_type]
    if "enum" in node:
        converted["enum"] = list(node["enum"])
    if "properties" in node:
        converted["properties"] = {
            key: to_gemini_schema(value) for key, value in node["properties"].items()
        }
    if "items" in node:
        converted["items"] = to_gemini_schema(node["items"])
    if "required" in node:
        converted["required"] = list(node["required"])
    return converted


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError))


def _classify(provider: str, exc: Exception) -> ProviderError:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return ProviderError(
            provider,
            transient=status == 429 or status >= 500,
            rate_limited=status == 429,
            detail=f"HTTP {status}",
        )
    if isinstance(exc, httpx.HTTPError):
        return ProviderError(
            provider, transient=True, rate_limited=False, detail=type(exc).__name__
        )
    return ProviderError(provider, transient=False, rate_limited=False, detail=type(exc).__name__)


class GeminiClient:
    name = "Gemini"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.GEMINI_BASE_URL,
            timeout=REQUEST_TIMEOUT,
            headers={"x-goog-api-key": settings.GEMINI_API_KEY},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, max=2),
        reraise=True,
    )
    async def _post(self, body: dict[str, Any]) -> httpx.Response:
        resp = await self._client.post(
            f"/models/{settings.GEMINI_MODEL}:generateContent", json=body
        )
        resp.raise_for_status()
        return resp

    async def generate_json(
        self, *, system: str, user_text: str, response_schema: dict[str, Any]
    ) -> Any:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": to_gemini_schema(response_schema),
                "temperature": 0.0,
            },
        }
        try:
            payload = (await self._post(body)).json()
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except Exception as exc:
            raise _classify(self.name, exc) from exc


class CerebrasClient:
    name = "Cerebras"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.CEREBRAS_BASE_URL,
            timeout=REQUEST_TIMEOUT,
            headers={"Authorization": f"Bearer {settings.CEREBRAS_API_KEY}"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, max=2),
        reraise=True,
    )
    async def _post(self, body: dict[str, Any]) -> httpx.Response:
        resp = await self._client.post("/chat/completions", json=body)
        resp.raise_for_status()
        return resp

    async def generate_json(
        self, *, system: str, user_text: str, response_schema: dict[str, Any]
    ) -> Any:
        body = {
            "model": settings.CEREBRAS_MODEL,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "query_intent",
                    "strict": True,
                    "schema": response_schema,
                },
            },
        }
        try:
            payload = (await self._post(body)).json()
            return json.loads(payload["choices"][0]["message"]["content"])
        except Exception as exc:
            raise _classify(self.name, exc) from exc


_clients: list[JsonLlm] | None = None
_tripped: dict[str, float] = {}
_active = ""


def _build() -> list[JsonLlm]:
    built: list[JsonLlm] = [GeminiClient()]
    if settings.CEREBRAS_API_KEY:
        built.append(CerebrasClient())
    return built


def clients() -> list[JsonLlm]:
    global _clients
    if _clients is None:
        _clients = _build()
    return _clients


def active_name() -> str:
    return _active or clients()[0].name


def _ordered() -> list[JsonLlm]:
    now = monotonic()
    ready = [client for client in clients() if _tripped.get(client.name, 0.0) <= now]
    return ready or list(clients())


async def generate_json(*, system: str, user_text: str, response_schema: dict[str, Any]) -> Any:
    global _active
    last: ProviderError | None = None
    for client in _ordered():
        try:
            data = await client.generate_json(
                system=system, user_text=user_text, response_schema=response_schema
            )
        except ProviderError as exc:
            last = exc
            logger.warning(
                "agent.llm.failed",
                provider=exc.provider,
                transient=exc.transient,
                detail=str(exc),
            )
            if not exc.transient:
                break
            _tripped[client.name] = monotonic() + TRIP_SECONDS
            continue
        _tripped.pop(client.name, None)
        _active = client.name
        return data
    if last is not None and last.rate_limited:
        raise RateLimited()
    raise AgentIntentUnavailable()


async def close_clients() -> None:
    global _clients, _active
    for client in _clients or []:
        await client.aclose()
    _clients = None
    _tripped.clear()
    _active = ""
