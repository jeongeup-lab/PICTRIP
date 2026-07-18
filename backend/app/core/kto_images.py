from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlparse

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
