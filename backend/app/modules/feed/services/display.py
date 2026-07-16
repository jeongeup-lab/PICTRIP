"""Type1 이미지의 표시 URL 결정 — 서명 변환(t1) 또는 무변형 pass-through.

폭 1620 = KTO 원본(~1620px)의 scale-down 상한. 일반 원본은 리사이즈 없이 WebP
재인코딩만 일어나 해상도 손실 없이 바이트가 줄어든다. 카드 cover는 높이가
병목이라 이보다 작은 폭은 원본 대비 유효 해상도를 깎는다.
"""

from __future__ import annotations

from app.config import settings
from app.core.kto_images import hires_kto_image, t1_transform_url

T1_WIDTH = 1620
T1_TILE_WIDTH = 320


def t1_display_url(
    image_url: str | None, cpyrht_div_cd: str | None, *, width: int = T1_WIDTH
) -> str | None:
    if image_url and cpyrht_div_cd == "Type1":
        transformed = t1_transform_url(
            hires_kto_image(image_url),
            width=width,
            secret=settings.IMG_PROXY_T1_SECRET,
            origin=settings.IMG_PROXY_ORIGIN,
        )
        if transformed:
            return transformed
    return image_url
