from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.core.db import DbSession
from app.core.redis import RedisDep
from app.kto.client import KtoDep
from app.modules.feed.schemas import (
    ChannelCard,
    ChannelCardsResponse,
    ChannelMeta,
    ChannelsResponse,
    MatchCard,
    MatchesResponse,
    PostsResponse,
)
from app.modules.feed.services import channels, matching, posts
from app.modules.feed.services.display import t1_display_url
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
