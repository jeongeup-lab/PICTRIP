from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_TIMEOUT = httpx.Timeout(25.0, connect=5.0)


async def generate_json(
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    temperature: float = 0.4,
) -> dict[str, Any] | None:
    if not settings.GEMINI_API_KEY:
        logger.warning("plan.llm.no_key")
        return None

    url = f"{settings.GEMINI_BASE_URL}/models/{settings.GEMINI_MODEL}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                url,
                json=body,
                headers={"x-goog-api-key": settings.GEMINI_API_KEY},
            )
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("plan.llm.request_failed", error=str(exc))
        return None

    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("plan.llm.bad_response", error=str(exc))
        return None
    return parsed if isinstance(parsed, dict) else None
