from __future__ import annotations

import base64
import json
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
from app.modules.plan.errors import PlanLlmBusy, PlanLlmUnavailable

logger = get_logger(__name__)


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError))


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
        response_schema: dict[str, Any],
    ) -> Any:
        parts: list[dict[str, Any]] = []
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
            logger.warning("plan.llm.failed", error_type=type(exc).__name__)
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                raise PlanLlmBusy() from exc
            raise PlanLlmUnavailable() from exc


_client: GeminiClient | None = None


def get_client() -> GeminiClient:
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
