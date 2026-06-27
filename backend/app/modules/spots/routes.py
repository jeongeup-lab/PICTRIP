"""SPT routes. Endpoints mirror API spec §7."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.core.db import DbSession
from app.core.kto_client import KtoDep
from app.core.redis import RedisDep
from app.core.schemas import ok
from app.modules.spots.schemas import (
    CurationDetailResponse,
    HomeFeedResponse,
    HomeHero,
    HomeRail,
    SpotCard,
    SpotDetailResponse,
    SpotImageOut,
    SpotIntro,
)
from app.modules.spots.services import curations as curation_svc
from app.modules.spots.services import feed, load_spot_detail

router = APIRouter(tags=["SPT · spots"])


@router.get("/home/feed", summary="Home feed (6 region heroes + 3 mood rails)")
async def home_feed(session: DbSession, redis: RedisDep) -> dict[str, Any]:
    row = await feed.assemble_home_feed(session, redis)
    payload = HomeFeedResponse(
        heroes=[
            HomeHero(
                id=h.id,
                slug=h.slug,
                title=h.title,
                subtitle=h.subtitle,
                coverUrl=h.cover_url,
            )
            for h in row.heroes
        ],
        rails=[
            HomeRail(
                id=rail.id,
                title=rail.title,
                subtitle=rail.subtitle,
                spots=[
                    SpotCard(
                        contentId=s.content_id,
                        title=s.title,
                        firstImageUrl=s.first_image_url,
                        addr1=s.addr1,
                        mapx=s.mapx,
                        mapy=s.mapy,
                        category=s.lcls_systm3_nm,
                    )
                    for s in rail.spots
                ],
            )
            for rail in row.rails
        ],
    )
    return ok(payload)


@router.get("/curations/{slug}", summary="Region/curation detail (≤8 spots)")
async def get_curation(slug: str, session: DbSession, redis: RedisDep) -> dict[str, Any]:
    row = await curation_svc.get_curation_detail(session, redis, slug)
    payload = CurationDetailResponse(
        id=row.id,
        type=row.type,
        slug=row.slug,
        title=row.title,
        lead=row.lead,
        intro=row.intro,
        coverUrl=row.cover_url,
        spots=[
            SpotCard(
                contentId=s.content_id,
                title=s.title,
                firstImageUrl=s.first_image_url,
                addr1=s.addr1,
                mapx=s.mapx,
                mapy=s.mapy,
                category=s.lcls_systm3_nm,
            )
            for s in row.spots
        ],
    )
    return ok(payload)


@router.get(
    "/spots/{content_id}",
    status_code=status.HTTP_200_OK,
    summary="Spot detail (overview/images lazy KTO fetch + 7-day cache)",
)
async def get_spot(
    content_id: str, session: DbSession, kto: KtoDep, redis: RedisDep
) -> dict[str, Any]:
    row = await load_spot_detail(session, kto, redis, content_id)
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
