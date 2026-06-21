"""SPT routes. Endpoints mirror API spec §7."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, status

from app.core.db import DbSession
from app.core.exceptions import ValidationFailed
from app.core.kto_client import KtoDep
from app.core.redis import RedisDep
from app.core.schemas import ok
from app.modules.spots.schemas import (
    MoodOut,
    MoodTag,
    RegionOut,
    RelatedSpot,
    SimilarNeighbor,
    SimilarQuery,
    SimilarResult,
    SpotCard,
    SpotDetailResponse,
    SpotImageOut,
    SpotIntro,
    TrendingSpot,
)
from app.modules.spots.services import (
    count_spots_per_mood,
    find_similar_spots,
    list_moods,
    list_regions,
    list_related_spots,
    list_spots_by_mood,
    list_spots_by_region,
    list_trending,
    load_active_spot_cards_by_ids,
    load_spot_detail,
    search_spots,
)

router = APIRouter(tags=["SPT · spots"])


@router.get(
    "/moods",
    status_code=status.HTTP_200_OK,
    summary="List of 8 moods",
)
async def get_moods(session: DbSession) -> dict[str, Any]:
    moods = await list_moods(session)
    counts = await count_spots_per_mood(session)
    return ok(
        [
            MoodOut(
                code=m.code,
                name=m.name,
                emoji=m.emoji,
                sortOrder=m.sort_order,
                spotsCount=counts.get(m.id, 0),
            )
            for m in moods
        ]
    )


@router.get(
    "/regions",
    status_code=status.HTTP_200_OK,
    summary="List of 17 sido/provinces (for the region filter)",
)
async def get_regions(session: DbSession) -> dict[str, Any]:
    regions = await list_regions(session)
    return ok([RegionOut(code=r.ldong_regn_cd, name=r.ldong_regn_nm) for r in regions])


@router.get(
    "/moods/{mood_code}/spots",
    status_code=status.HTTP_200_OK,
    summary="Random spot list by mood (for the photo grid)",
)
async def get_mood_spots(
    mood_code: str,
    session: DbSession,
    limit: int = Query(default=8, ge=1, le=10000),
    region: str | None = Query(default=None),
) -> dict[str, Any]:
    rows = await list_spots_by_mood(session, mood_code, limit=limit, region=region)
    return ok(
        [
            SpotCard(
                contentId=r.content_id,
                title=r.title,
                firstImageUrl=r.first_image_url,
                addr1=r.addr1,
                mapx=r.mapx,
                mapy=r.mapy,
            )
            for r in rows
        ]
    )


# NOTE: declared before "/spots/{content_id}" so the literal "trending" segment
# is not captured as a content_id by the detail route.
#
# 의도적 미소비 상태: 모바일 클라이언트는 현재 이 엔드포인트를 호출하지 않는다
# (구 trending store는 #19에서 제거). KTO 데이터 활용(집중률 TOP, ADR-0016) 공모전
# 데모 surface로 유지한다 — "죽은 코드"로 오인해 삭제하지 말 것.
@router.get(
    "/spots/trending",
    status_code=status.HTTP_200_OK,
    summary="전국 집중률 TOP (KTO 관광지 집중률 desc, ADR-0016)",
)
async def get_trending_spots(
    session: DbSession,
    limit: int = Query(default=10, ge=1, le=100),
    region: str | None = Query(default=None),
) -> dict[str, Any]:
    rows = await list_trending(session, limit=limit, region=region)
    return ok(
        [
            TrendingSpot(
                contentId=r.content_id,
                title=r.title,
                firstImageUrl=r.first_image_url,
                addr1=r.addr1,
                regionName=r.region_name,
                mapx=r.mapx,
                mapy=r.mapy,
                concentrationRate=r.concentration_rate,
                rank=r.rank,
            )
            for r in rows
        ]
    )


# NOTE: declared before "/spots/{content_id}" so the literal "search" segment is
# not captured as a content_id by the detail route.
@router.get(
    "/spots/search",
    status_code=status.HTTP_200_OK,
    summary="Place-name text search (title/addr1 ILIKE, region filter)",
)
async def search_spots_route(
    session: DbSession,
    q: str = Query(..., min_length=1, max_length=80, description="Search term (place name)"),
    limit: int = Query(default=20, ge=1, le=50),
    region: str | None = Query(default=None),
) -> dict[str, Any]:
    rows = await search_spots(session, q, limit=limit, region=region)
    return ok(
        [
            SpotCard(
                contentId=r.content_id,
                title=r.title,
                firstImageUrl=r.first_image_url,
                addr1=r.addr1,
                mapx=r.mapx,
                mapy=r.mapy,
            )
            for r in rows
        ]
    )


def _csv(value: str | None) -> list[str]:
    """Split a comma-separated query param into a clean code list."""
    if not value:
        return []
    return [c.strip() for c in value.split(",") if c.strip()]


@router.get(
    "/spots/by-region",
    status_code=status.HTTP_200_OK,
    summary="지역(시군구/시도 코드 union)별 대표 스폿 — 집중률 desc, 이미지 only",
)
async def get_spots_by_region(
    session: DbSession,
    signgu: str | None = Query(default=None, description="시군구 코드 CSV (ldong_signgu_cd)"),
    regn: str | None = Query(default=None, description="시도 코드 CSV (ldong_regn_cd)"),
    limit: int = Query(default=24, ge=1, le=60),
) -> dict[str, Any]:
    signgu_codes = _csv(signgu)
    regn_codes = _csv(regn)
    if not signgu_codes and not regn_codes:
        raise ValidationFailed("signgu 또는 regn 중 하나는 필수입니다.")
    rows = await list_spots_by_region(
        session, signgu_codes=signgu_codes, regn_codes=regn_codes, limit=limit
    )
    return ok(
        [
            SpotCard(
                contentId=r.content_id,
                title=r.title,
                firstImageUrl=r.first_image_url,
                addr1=r.addr1,
                mapx=r.mapx,
                mapy=r.mapy,
                category=r.category,
            )
            for r in rows
        ]
    )


@router.get(
    "/spots/batch",
    status_code=status.HTTP_200_OK,
    summary="content_id 목록 배치 조회 — 입력 순서 보존, 손으로 고른 레일용",
)
async def get_spots_batch(
    session: DbSession,
    ids: str = Query(..., description="content_id CSV (1~30개)"),
) -> dict[str, Any]:
    id_list = _csv(ids)
    if not id_list:
        raise ValidationFailed("ids는 비어 있을 수 없습니다.")
    if len(id_list) > 30:
        raise ValidationFailed("ids는 최대 30개입니다.")
    cards = await load_active_spot_cards_by_ids(session, id_list)
    ordered = [cards[i] for i in id_list if i in cards]
    return ok(
        [
            SpotCard(
                contentId=r.content_id,
                title=r.title,
                firstImageUrl=r.first_image_url,
                addr1=r.addr1,
                mapx=r.mapx,
                mapy=r.mapy,
                category=r.category,
            )
            for r in ordered
        ]
    )


@router.get(
    "/spots/{content_id}/similar",
    status_code=status.HTTP_200_OK,
    summary="Embedding-based similar top-N for the given spot",
)
async def get_similar_spots(
    content_id: str,
    session: DbSession,
    limit: int = Query(default=10, ge=1, le=30),
    region: str | None = Query(default=None),
) -> dict[str, Any]:
    result = await find_similar_spots(session, content_id, limit=limit, region=region)
    return ok(
        SimilarResult(
            query=SimilarQuery(
                contentId=result.query.content_id,
                title=result.query.title,
                firstImageUrl=result.query.first_image_url,
                addr1=result.query.addr1,
                mapx=result.query.mapx,
                mapy=result.query.mapy,
            ),
            neighbors=[
                SimilarNeighbor(
                    contentId=row.content_id,
                    title=row.title,
                    firstImageUrl=row.first_image_url,
                    addr1=row.addr1,
                    mapx=row.mapx,
                    mapy=row.mapy,
                    distance=distance,
                )
                for row, distance in result.neighbors
            ],
        )
    )


@router.get(
    "/spots/{content_id}/related",
    status_code=status.HTTP_200_OK,
    summary="Places people search together (KTO TarRlteTar live + Redis 1h, ADR-0005/0015)",
)
async def get_related_spots(
    content_id: str,
    session: DbSession,
    kto: KtoDep,
    redis: RedisDep,
) -> dict[str, Any]:
    rows = await list_related_spots(session, kto, redis, content_id)
    return ok(
        [
            RelatedSpot(
                name=r.name,
                category=r.category,
                regionName=r.region_name,
                address=r.address,
                rank=r.rank,
                contentId=r.content_id,
            )
            for r in rows
        ]
    )


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
