"""SPT routes. Endpoints mirror API spec §7."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.core.db import DbSession
from app.core.kto_client import KtoDep
from app.core.schemas import ok
from app.modules.spots.schemas import (
    MoodTag,
    SpotDetailResponse,
    SpotImageOut,
    SpotIntro,
)
from app.modules.spots.services import load_spot_detail

router = APIRouter(tags=["SPT · spots"])


@router.get(
    "/spots/{content_id}",
    status_code=status.HTTP_200_OK,
    summary="Spot detail (overview/images lazy KTO fetch + 7-day cache)",
)
async def get_spot(content_id: str, session: DbSession, kto: KtoDep) -> dict[str, Any]:
    row = await load_spot_detail(session, kto, content_id)
    payload = SpotDetailResponse(
        contentId=row.content_id,
        title=row.title,
        firstImageUrl=row.first_image_url,
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
        moods=[MoodTag(code=m.code, name=m.name, emoji=m.emoji) for m in row.moods],
        images=[
            SpotImageOut(originImageUrl=i.origin_image_url, smallImageUrl=i.small_image_url)
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
