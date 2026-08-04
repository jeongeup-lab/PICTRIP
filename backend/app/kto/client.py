from __future__ import annotations

import hashlib
import hmac
from enum import StrEnum
from typing import Annotated, Any
from urllib.parse import urlparse

import httpx
from fastapi import Depends, Request
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.core.logging import get_logger
from app.web.errors import KtoApiUnavailable

logger = get_logger(__name__)


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError))


class KtoService(StrEnum):
    KOR = "KorService2"
    TARRLTE = "TarRlteTarService1"
    CNCTR = "TatsCnctrRateService"
    PET = "KorPetTourService2"
    GALLERY = "PhotoGalleryService1"


_SERVICE_BASE: dict[KtoService, str] = {
    KtoService.KOR: settings.KTO_BASE_URL_KOR,
    KtoService.TARRLTE: settings.KTO_BASE_URL_TARRLTE,
    KtoService.CNCTR: settings.KTO_BASE_URL_CNCTR,
    KtoService.PET: settings.KTO_BASE_URL_PET,
    KtoService.GALLERY: settings.KTO_BASE_URL_GALLERY,
}


class KtoClient:
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
        retry=retry_if_exception(_is_transient),
        reraise=True,
    )
    async def call(
        self,
        service: KtoService,
        operation: str,
        **params: Any,
    ) -> list[dict[str, Any]]:
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
                "kto.call.failed",
                service=service.value,
                operation=operation,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise KtoApiUnavailable() from e

        body = resp.json().get("response", {}).get("body", {})
        items = body.get("items")
        if not items or items == "":
            return []
        item = items.get("item", [])
        return item if isinstance(item, list) else [item]


def get_kto(request: Request) -> KtoClient:
    kto: KtoClient = request.app.state.kto
    return kto


KtoDep = Annotated[KtoClient, Depends(get_kto)]

KTO_IMAGE_HOST = "tong.visitkorea.or.kr"


def _is_kto_host(url: str) -> bool:
    return urlparse(url).hostname == KTO_IMAGE_HOST


def https_kto_image(url: str | None) -> str | None:
    if url and url.startswith("http://") and _is_kto_host(url):
        return "https://" + url[len("http://") :]
    return url


def t1_transform_url(url: str | None, *, width: int, secret: str, origin: str) -> str | None:
    if not url or not secret:
        return None
    upgraded = https_kto_image(url)
    if not upgraded or not _is_kto_host(upgraded):
        return None
    parsed = urlparse(upgraded)
    target = f"{parsed.hostname}{parsed.path}"
    if parsed.query:
        target = f"{target}?{parsed.query}"
    payload = f"{width}/{target}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{origin}/t1/{width}/{sig}/{target}"


def hires_kto_image(url: str | None) -> str | None:
    upgraded = https_kto_image(url)
    if upgraded and _is_kto_host(upgraded):
        return upgraded.replace("_image2_1", "_image1_1")
    return upgraded
