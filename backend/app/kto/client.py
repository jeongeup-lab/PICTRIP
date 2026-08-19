from __future__ import annotations

import hashlib
import hmac
import re
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
from app.web.errors import KtoApiUnavailable, KtoQuotaExhausted

logger = get_logger(__name__)

OK_RESULT_CODE = "0000"
QUOTA_ERROR_MARKERS = (
    "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR",
    "SERVICE_ACCESS_DENIED_ERROR",
)


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError))


_SERVICE_KEY_PATTERN = re.compile(r"serviceKey=[^&\s'\"]+")


def redact_service_key(text: str) -> str:
    return _SERVICE_KEY_PATTERN.sub("serviceKey=***", text)


def _quota_exhausted(body_text: str) -> bool:
    return any(marker in body_text for marker in QUOTA_ERROR_MARKERS)


class KtoService(StrEnum):
    KOR = "KorService2"
    TARRLTE = "TarRlteTarService1"
    CNCTR = "TatsCnctrRateService"
    PET = "KorPetTourService2"
    GALLERY = "PhotoGalleryService1"


DATA_GO_KR_HOST = "apis.data.go.kr"


def https_data_go_kr(base_url: str) -> str:
    if base_url.startswith("http://") and urlparse(base_url).hostname == DATA_GO_KR_HOST:
        return "https://" + base_url[len("http://") :]
    return base_url


_SERVICE_BASE: dict[KtoService, str] = {
    KtoService.KOR: https_data_go_kr(settings.KTO_BASE_URL_KOR),
    KtoService.TARRLTE: https_data_go_kr(settings.KTO_BASE_URL_TARRLTE),
    KtoService.CNCTR: https_data_go_kr(settings.KTO_BASE_URL_CNCTR),
    KtoService.PET: https_data_go_kr(settings.KTO_BASE_URL_PET),
    KtoService.GALLERY: https_data_go_kr(settings.KTO_BASE_URL_GALLERY),
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
    async def _request(self, url: str, params: dict[str, Any]) -> httpx.Response:
        """재시도 판정이 가능하도록 httpx 예외를 감싸지 않고 그대로 올린다."""
        resp = await self._client.get(url, params=params)
        if resp.status_code == 429 and _quota_exhausted(resp.text):
            raise KtoQuotaExhausted()
        resp.raise_for_status()
        return resp

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
            resp = await self._request(url, merged)
        except KtoQuotaExhausted:
            logger.warning("kto.call.quota_exhausted", service=service.value, operation=operation)
            raise
        except httpx.HTTPError as e:
            logger.warning(
                "kto.call.failed",
                service=service.value,
                operation=operation,
                error_type=type(e).__name__,
                error=redact_service_key(str(e)),
            )
            raise KtoApiUnavailable() from e

        return self._items(resp, service=service, operation=operation)

    def _items(
        self, resp: httpx.Response, *, service: KtoService, operation: str
    ) -> list[dict[str, Any]]:
        try:
            payload = resp.json()
        except ValueError:
            if _quota_exhausted(resp.text):
                logger.warning(
                    "kto.call.quota_exhausted", service=service.value, operation=operation
                )
                raise KtoQuotaExhausted() from None
            logger.warning("kto.call.unparsable", service=service.value, operation=operation)
            raise KtoApiUnavailable() from None
        if not isinstance(payload, dict):
            raise KtoApiUnavailable()
        if "response" not in payload:
            if _quota_exhausted(resp.text):
                logger.warning(
                    "kto.call.quota_exhausted", service=service.value, operation=operation
                )
                raise KtoQuotaExhausted()
            logger.warning(
                "kto.call.rejected",
                service=service.value,
                operation=operation,
                result_code=payload.get("resultCode"),
                result_msg=payload.get("resultMsg"),
            )
            raise KtoApiUnavailable()
        envelope = payload["response"]
        result_code = envelope.get("header", {}).get("resultCode")
        if result_code not in (OK_RESULT_CODE, None):
            logger.warning(
                "kto.call.rejected",
                service=service.value,
                operation=operation,
                result_code=result_code,
                result_msg=envelope.get("header", {}).get("resultMsg"),
            )
            raise KtoApiUnavailable()
        items = envelope.get("body", {}).get("items")
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
