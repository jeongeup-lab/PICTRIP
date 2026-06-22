"""Generic Kakao Local REST helper.

KAKAO_REST_API_KEY stays server-side. Domain modules own endpoint-specific
payload parsing, caching, and graceful fallback semantics.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://dapi.kakao.com/v2/local"
_TIMEOUT = httpx.Timeout(5.0, connect=3.0)


async def kakao_local_get(path: str, *, params: Mapping[str, Any]) -> dict[str, Any] | None:
    """GET a Kakao Local endpoint and return decoded JSON, or None on failure."""
    if not settings.KAKAO_REST_API_KEY:
        logger.warning("kakao.local.no_key", path=path)
        return None

    normalized_path = path if path.startswith("/") else f"/{path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_BASE_URL}{normalized_path}",
                params=params,
                headers={"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"},
            )
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("kakao.local.request_failed", path=path, error=str(exc))
        return None

    return payload if isinstance(payload, dict) else None
