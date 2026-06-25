"""KTO image URL normalization: upgrade http->https for the KTO host (iOS ATS blocks http image loads).

Transport-only upgrade of the same URL — stays within the KTO "URLs verbatim / no download" policy.
"""

from __future__ import annotations

KTO_IMAGE_HOST = "tong.visitkorea.or.kr"


def https_kto_image(url: str | None) -> str | None:
    """Upgrade http->https for the KTO host only; other URLs returned unchanged."""
    if url and url.startswith("http://") and KTO_IMAGE_HOST in url:
        return "https://" + url[len("http://") :]
    return url
