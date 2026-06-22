"""KTO image URL normalization.

KTO's `firstImageUrl` (and detail image URLs) arrive over a mix of http:// and
https://. iOS ATS blocks plain http:// loads in expo-image — the
``NSAllowsArbitraryLoadsInMedia`` exception only covers AVFoundation media, not
NSURLSession image downloads — so roughly half the photos render blank on iOS.

KTO serves the same asset over https, so we upgrade the scheme for the KTO host
only. This is a transport upgrade of the same URL, not a content rewrite, and
stays within the "URLs verbatim / no download" KTO policy.
"""

from __future__ import annotations

KTO_IMAGE_HOST = "tong.visitkorea.or.kr"


def https_kto_image(url: str | None) -> str | None:
    """Return ``url`` with http:// upgraded to https:// for the KTO host only.

    Non-KTO hosts and already-https URLs are returned unchanged.
    """
    if url and url.startswith("http://") and KTO_IMAGE_HOST in url:
        return "https://" + url[len("http://") :]
    return url
