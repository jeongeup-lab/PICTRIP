from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.core.db import DbSession
from app.core.redis import RedisDep
from app.core.schemas import ok
from app.modules.feed.schemas import MatchCard, MatchesResponse, PostsResponse
from app.modules.feed.services import matching, posts

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
                    imageUrl=r.image_url,
                    overviewFirst=r.overview_first,
                )
                for r in rows
            ],
        )
    )


def _to_response(page: posts.PostsPageRow) -> PostsResponse:
    return PostsResponse(
        seed=page.seed,
        items=[posts.to_post(r) for r in page.items],
        nextCursor=page.next_cursor,
        hasMore=page.has_more,
    )
