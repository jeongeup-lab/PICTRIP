"""Async client for the four KTO Open APIs.

Wraps httpx with shared params, retry, and response unwrapping. Calls are traced
via structured logging; the client stays thin (no DB writes).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any

import httpx
from fastapi import Depends, Request
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.core.exceptions import KtoApiUnavailable
from app.core.logging import get_logger

logger = get_logger(__name__)


class KtoService(StrEnum):
    KOR = "KorService2"
    TARRLTE = "TarRlteTarService1"
    CNCTR = "TatsCnctrRateService"
    DATALAB = "DataLabService"


_SERVICE_BASE: dict[KtoService, str] = {
    KtoService.KOR: settings.KTO_BASE_URL_KOR,
    KtoService.TARRLTE: settings.KTO_BASE_URL_TARRLTE,
    KtoService.CNCTR: settings.KTO_BASE_URL_CNCTR,
    KtoService.DATALAB: settings.KTO_BASE_URL_DATALAB,
}


class KtoClient:
    """Thin async wrapper. Instantiate once and reuse — kept in app.state.kto."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            headers={"User-Agent": f"{settings.KTO_MOBILE_APP}/1.0"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def call(
        self,
        service: KtoService,
        operation: str,
        **params: Any,
    ) -> list[dict[str, Any]]:
        """Call a KTO endpoint and return the unwrapped item list (may be empty)."""
        url = f"{_SERVICE_BASE[service]}/{operation}"
        merged = {
            "serviceKey": settings.KTO_SERVICE_KEY,
            "MobileOS": "ETC",
            "MobileApp": settings.KTO_MOBILE_APP,
            "_type": "json",
            **{k: v for k, v in params.items() if v is not None},
        }
        try:
            resp = await self._client.get(url, params=merged)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(
                "kto.call.failed", service=service.value, operation=operation, error=str(e)
            )
            raise KtoApiUnavailable() from e

        body = resp.json().get("response", {}).get("body", {})
        items = body.get("items")
        if not items or items == "":
            return []
        item = items.get("item", [])
        return item if isinstance(item, list) else [item]


def get_kto(request: Request) -> KtoClient:
    """FastAPI dependency. Returns the lifespan-installed KtoClient singleton."""
    kto: KtoClient = request.app.state.kto
    return kto


KtoDep = Annotated[KtoClient, Depends(get_kto)]
