from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.core.db import DbSession
from app.core.redis import RedisDep
from app.kto.client import KtoDep
from app.kto.display import t1_display_url
from app.modules.feed.repositories import ShortRow
from app.modules.feed.schemas import (
    ChannelCard,
    ChannelCardsResponse,
    ChannelMeta,
    ChannelsResponse,
    HomeCardsResponse,
    HomeSpotCard,
    MatchCard,
    MatchesResponse,
    PostsResponse,
    RecommendationsResponse,
    ShortsCard,
    ShortsResponse,
    ShortsSpotCard,
)
from app.modules.feed.services import channels, home, matching, posts, shorts
from app.security.jwt import CurrentUserId
from app.web.envelope import ok

router = APIRouter(tags=["feed"])


@router.get("/feed")
async def feed(
    session: DbSession,
    seed: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(6, ge=1, le=20),
) -> dict[str, Any]:
    page = await posts.list_posts(session, seed=seed, cursor=cursor, limit=limit)
    return ok(_to_response(page))


@router.get("/explore")
async def explore(
    session: DbSession,
    seed: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(30, ge=1, le=60),
) -> dict[str, Any]:
    page = await posts.list_posts(session, seed=seed, cursor=cursor, limit=limit)
    return ok(_to_response(page))


@router.get("/shorts")
async def shorts_feed(
    session: DbSession,
    cursor: str | None = Query(None),
    limit: int = Query(6, ge=1, le=20),
) -> dict[str, Any]:
    page = await shorts.list_shorts(session, cursor=cursor, limit=limit)
    return ok(
        ShortsResponse(
            items=[_shorts_card(page, row) for row in page.items],
            nextCursor=page.next_cursor,
            hasMore=page.has_more,
        )
    )


def _shorts_card(page: shorts.ShortsPageRow, row: ShortRow) -> ShortsCard:
    cards = []
    for spot in page.spots_by_video.get(row.video_id, []):
        region_name, sigungu_name = page.region_by_content.get(spot.content_id, (None, None))
        cards.append(
            ShortsSpotCard(
                contentId=spot.content_id,
                title=spot.title,
                regionLabel=" ".join(p for p in (region_name, sigungu_name) if p),
                imageUrl=t1_display_url(spot.first_image_url, spot.cpyrht_div_cd),
            )
        )
    return ShortsCard(
        videoId=row.video_id,
        title=row.title,
        channelTitle=row.channel_title,
        thumbnailUrl=row.thumbnail_url,
        viewCount=row.view_count,
        anchorLabel=row.anchor_label,
        spots=cards,
    )


@router.get("/overseas/{overseas_id}/matches")
async def overseas_matches(
    session: DbSession,
    redis: RedisDep,
    overseas_id: int,
) -> dict[str, Any]:
    rows = await matching.find_matches(session, redis, overseas_id)
    return ok(
        MatchesResponse(
            overseasId=overseas_id,
            matches=[
                MatchCard(
                    contentId=r.content_id,
                    title=r.title,
                    regionLabel=r.region_label,
                    imageUrl=matching.display_image_url(r),
                    overviewFirst=r.overview_first,
                )
                for r in rows
            ],
        )
    )


@router.get("/home/nearby", summary="지금 주변 인기 장소 (혼잡도 랭킹 + 거리)")
async def home_nearby(
    session: DbSession,
    redis: RedisDep,
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    limit: int = Query(home.CARD_COUNT, ge=1, le=20),
) -> dict[str, Any]:
    ranking = await home.load_nearby_ranked(session, redis, lat=lat, lng=lng, limit=limit)
    return ok(_home_cards(ranking))


@router.get("/home/trending", summary="전국 인기 (혼잡도 상위)")
async def home_trending(
    session: DbSession,
    redis: RedisDep,
    limit: int = Query(home.CARD_COUNT, ge=1, le=20),
) -> dict[str, Any]:
    ranking = await home.load_trending(session, redis, limit=limit)
    return ok(_home_cards(ranking))


@router.get("/home/taste-picks", summary="취향 카드 후보 (저장하면 AI 추천 시드)")
async def home_taste_picks(
    session: DbSession,
    redis: RedisDep,
    limit: int = Query(home.TASTE_PICK_COUNT, ge=1, le=30),
) -> dict[str, Any]:
    rows = await home.load_taste_picks(session, redis, limit=limit)
    return ok(HomeCardsResponse(items=[_home_card(r) for r in rows]))


@router.get("/home/recommendations", summary="저장한 장소 임베딩 기반 AI 추천")
async def home_recommendations(
    session: DbSession,
    user_id: CurrentUserId,
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    limit: int = Query(home.CARD_COUNT, ge=1, le=20),
) -> dict[str, Any]:
    result = await home.load_recommendations(
        session, user_id=user_id, lat=lat, lng=lng, limit=limit
    )
    return ok(
        RecommendationsResponse(
            ready=result.ready,
            savedCount=result.saved_count,
            minSaved=result.min_saved,
            items=[_home_card(r) for r in result.items],
        )
    )


def _home_cards(ranking: home.HomeRanking) -> HomeCardsResponse:
    return HomeCardsResponse(
        items=[_home_card(r) for r in ranking.cards],
        baseDate=ranking.base_date,
    )


def _home_card(row: home.HomeCardRow) -> HomeSpotCard:
    return HomeSpotCard(
        contentId=row.content_id,
        title=row.title,
        regionLabel=row.region_label,
        imageUrl=row.image_url,
        rank=row.rank,
        dist=row.dist,
        category=row.category,
        tag=row.tag,
        anchorTitle=row.anchor_title,
    )


@router.get("/home/channels")
async def home_channels(
    session: DbSession,
    redis: RedisDep,
    kto: KtoDep,
) -> dict[str, Any]:
    metas = await channels.load_channel_metas(session, redis, kto)
    return ok(
        ChannelsResponse(
            channels=[
                ChannelMeta(
                    key=m.key,
                    label=m.label,
                    thumbnailUrl=m.thumbnail_url,
                    available=m.available,
                )
                for m in metas
            ]
        )
    )


@router.get("/home/channels/{key}")
async def home_channel_cards(
    session: DbSession,
    redis: RedisDep,
    kto: KtoDep,
    key: str,
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
) -> dict[str, Any]:
    rows = await channels.load_channel_cards(session, redis, kto, key=key, lat=lat, lng=lng)
    return ok(
        ChannelCardsResponse(
            key=key,
            label=channels.CHANNEL_LABELS[key],
            cards=[_channel_card(r) for r in rows],
        )
    )


def _channel_card(row: channels.ChannelCardRow) -> ChannelCard:
    return ChannelCard(
        contentId=row.content_id,
        title=row.title,
        regionLabel=row.region_label,
        imageUrl=t1_display_url(row.image_url, row.cpyrht_div_cd),
        dist=row.dist,
        rank=row.rank,
        dday=row.dday,
        line=row.line,
        tag=row.tag,
        saveable=row.saveable,
    )


def _to_response(page: posts.PostsPageRow) -> PostsResponse:
    return PostsResponse(
        seed=page.seed,
        items=[posts.to_post(r) for r in page.items],
        nextCursor=page.next_cursor,
        hasMore=page.has_more,
    )
