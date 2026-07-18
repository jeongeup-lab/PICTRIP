from __future__ import annotations

from app.config import settings
from app.kto.client import hires_kto_image, t1_transform_url

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
