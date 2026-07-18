from __future__ import annotations

import json

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://api.odsay.com/v1/api/searchPubTransPathT"
_TIMEOUT = httpx.Timeout(5.0, connect=3.0)


async def transit_minutes(
    *, from_lat: float, from_lng: float, to_lat: float, to_lng: float
) -> int | None:
    if not settings.ODSAY_API_KEY:
        logger.warning("plan.odsay.no_key")
        return None

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _BASE_URL,
                params={
                    "SX": from_lng,
                    "SY": from_lat,
                    "EX": to_lng,
                    "EY": to_lat,
                    "apiKey": settings.ODSAY_API_KEY,
                },
            )
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("plan.odsay.request_failed", error=str(exc))
        return None

    try:
        paths = payload["result"]["path"]
        total = int(paths[0]["info"]["totalTime"])
    except (KeyError, IndexError, TypeError, ValueError):
        logger.warning("plan.odsay.bad_response")
        return None
    return total if total > 0 else None
