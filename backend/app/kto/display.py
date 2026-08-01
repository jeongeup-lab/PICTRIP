from __future__ import annotations

from app.config import settings
from app.kto.client import hires_kto_image, https_kto_image, t1_transform_url

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
    return https_kto_image(image_url)


def t1_thumb_url(origin_url: str, small_url: str | None, cpyrht_div_cd: str | None) -> str | None:
    if cpyrht_div_cd == "Type1":
        return t1_display_url(origin_url, cpyrht_div_cd, width=T1_TILE_WIDTH)
    if cpyrht_div_cd == "Type3":
        return https_kto_image(origin_url)
    return https_kto_image(small_url or origin_url)
