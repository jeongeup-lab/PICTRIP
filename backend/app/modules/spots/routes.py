from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, status

from app.core.db import DbSession
from app.core.redis import RedisDep
from app.kto.client import KtoDep
from app.kto.display import t1_display_url, t1_thumb_url
from app.modules.spots.schemas import (
    SpotDetailResponse,
    SpotImageOut,
    SpotIntro,
)
from app.modules.spots.services import load_spot_detail, refresh_spot_detail_in_background
from app.web.envelope import ok

router = APIRouter(tags=["SPT · spots"])
_DEFERRED_DETAIL_MODE = "deferred-v1"


@router.get(
    "/spots/{content_id}",
    status_code=status.HTTP_200_OK,
    summary="Spot detail (overview/images lazy KTO fetch + 90-day cache)",
)
async def get_spot(
    content_id: str,
    background_tasks: BackgroundTasks,
    session: DbSession,
    kto: KtoDep,
    redis: RedisDep,
    detail_mode: str | None = Header(default=None, alias="X-PicTrip-Detail-Mode"),
) -> dict[str, Any]:
    defer_refresh = detail_mode == _DEFERRED_DETAIL_MODE
    row = await load_spot_detail(session, kto, redis, content_id, defer_refresh=defer_refresh)
    if defer_refresh and row.detail_status in {"pending", "stale"}:
        background_tasks.add_task(refresh_spot_detail_in_background, kto, redis, content_id)
    payload = SpotDetailResponse(
        contentId=row.content_id,
        title=row.title,
        firstImageUrl=t1_display_url(row.first_image_url, row.cpyrht_div_cd),
        addr1=row.addr1,
        mapx=row.mapx,
        mapy=row.mapy,
        addr2=row.addr2,
        overview=row.overview,
        homepage=row.homepage,
        tel=row.tel,
        regionName=row.region_name,
        sigunguName=row.sigungu_name,
        detailStatus=row.detail_status,
        images=[
            SpotImageOut(
                originImageUrl=t1_display_url(i.origin_image_url, i.cpyrht_div_cd)
                or i.origin_image_url,
                smallImageUrl=t1_thumb_url(i.origin_image_url, i.small_image_url, i.cpyrht_div_cd),
            )
            for i in row.images
        ],
        category=row.category,
        intro=(
            SpotIntro(
                usetime=row.intro.usetime,
                restdate=row.intro.restdate,
                parking=row.intro.parking,
                infocenter=row.intro.infocenter,
                firstmenu=row.intro.firstmenu,
                treatmenu=row.intro.treatmenu,
            )
            if row.intro
            else None
        ),
    )
    return ok(payload)
