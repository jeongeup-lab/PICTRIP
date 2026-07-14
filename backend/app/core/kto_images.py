"""KTO image URL normalization: upgrade http->https for the KTO host (iOS ATS blocks http image loads).

Transport-only upgrade of the same URL — stays within the KTO "URLs verbatim / no download" policy.
"""

from __future__ import annotations

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
