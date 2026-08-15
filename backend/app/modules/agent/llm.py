from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from typing import Any

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


MAX_ERROR_BODY_CHARS = 500


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError))


def _failure_detail(exc: BaseException) -> str | None:
    if not isinstance(exc, httpx.HTTPStatusError):
        return None
    return exc.response.text[:MAX_ERROR_BODY_CHARS] or None


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
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,
    )
    async def _generate(self, body: dict[str, Any]) -> httpx.Response:
        resp = await self._client.post(
            f"/models/{settings.GEMINI_MODEL}:generateContent", json=body
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
            },
        }
        try:
            resp = await self._generate(body)
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


_client: GeminiClient | None = None


def get_client() -> GeminiClient:
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
