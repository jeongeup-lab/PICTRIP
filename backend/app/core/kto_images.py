"""KTO image URL normalization: upgrade http->https for the KTO host (iOS ATS blocks http image loads).

Transport-only upgrade of the same URL — stays within the KTO "URLs verbatim / no download" policy.
"""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlparse

KTO_IMAGE_HOST = "tong.visitkorea.or.kr"


def _is_kto_host(url: str) -> bool:
    """True only when the URL's actual host is the KTO image host — not when the host
    merely appears as a substring (e.g. embedded in a query param of a foreign URL)."""
    return urlparse(url).hostname == KTO_IMAGE_HOST


def https_kto_image(url: str | None) -> str | None:
    """Upgrade http->https when the URL's actual host is the KTO image host; other URLs
    (incl. foreign URLs that merely carry the KTO host in a query param) returned unchanged."""
    if url and url.startswith("http://") and _is_kto_host(url):
        return "https://" + url[len("http://") :]
    return url


def t1_transform_url(url: str | None, *, width: int, secret: str, origin: str) -> str | None:
    """Signed img-proxy transform URL (`{origin}/t1/{width}/{sig}/{host}{path}`) for a KTO
    image the 공공누리 license allows to be resized (`cpyrhtDivCd=Type1` — 출처표시).
    The HMAC keeps the public worker from ever transforming a Type3 (변경금지) image:
    only the backend, which holds the license column, can mint a valid signature.
    Returns None (caller keeps the pass-through URL) when the secret is unset or the
    URL is not KTO-hosted. Callers pass the license check — this function only signs."""
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
    """Point a KTO image URL at the larger `_image1_1` original (~1620px) instead of the
    `_image2_1` mid-size (940px) that `firstimage` returns. Transport-only swap of the same
    resource — stays within the KTO "URLs verbatim / no download" policy. http->https is also
    ensured; non-KTO URLs and None pass through unchanged. Apply only to large display surfaces
    (full-card / fullscreen). The `_image1_1` variant is missing on ~20% of older images (404),
    so clients MUST fall back to `_image2_1` on load error."""
    upgraded = https_kto_image(url)
    if upgraded and _is_kto_host(upgraded):
        return upgraded.replace("_image2_1", "_image1_1")
    return upgraded
