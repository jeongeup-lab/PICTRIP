"""USR routes. See API spec §5 + design 2026-05-27 §1."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Response, status

from app.core.auth import CurrentUserId
from app.core.db import DbSession
from app.core.redis import RedisDep
from app.core.schemas import ok
from app.modules.spots import services as spots_services
from app.modules.spots.schemas import SpotCard
from app.modules.users import services
from app.modules.users.schemas import KakaoCallbackIn, LogoutBody, RefreshBody, SavedSpotToggle

router = APIRouter(tags=["USR · user/auth"])


@router.post(
    "/auth/oauth/kakao",
    status_code=status.HTTP_200_OK,
    summary="Kakao OIDC id_token → internal token pair",
)
async def oauth_kakao(
    body: KakaoCallbackIn,
    session: DbSession,
    redis: RedisDep,
) -> dict[str, Any]:
    pair = await services.authenticate_with_kakao(session, redis, body)
    return ok(pair.model_dump())


@router.post(
    "/auth/refresh",
    status_code=status.HTTP_200_OK,
    summary="Refresh JWT rotation",
)
async def refresh(body: RefreshBody, session: DbSession, redis: RedisDep) -> dict[str, Any]:
    pair = await services.refresh_session(session, redis, body.refreshToken)
    return ok(pair.model_dump())


@router.post(
    "/auth/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout (idempotent)",
)
async def logout(body: LogoutBody, redis: RedisDep) -> dict[str, Any]:
    await services.logout_session(redis, body.refreshToken)
    return ok({})


@router.get(
    "/users/me",
    status_code=status.HTTP_200_OK,
    summary="My profile",
)
async def me(user_id: CurrentUserId, session: DbSession) -> dict[str, Any]:
    user = await services.get_user_public(session, user_id)
    return ok(user.model_dump())


@router.delete(
    "/users/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="회원 탈퇴 (account deletion — anonymize, unlink OAuth, revoke sessions)",
)
async def delete_me(
    user_id: CurrentUserId,
    session: DbSession,
    redis: RedisDep,
) -> Response:
    await services.delete_user_account(session, redis, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Saved spots / bookmarks (ADR-0011) ----------


@router.get(
    "/users/me/saved",
    status_code=status.HTTP_200_OK,
    summary="My saved spots list (spot card)",
)
async def list_saved(
    user_id: CurrentUserId,
    session: DbSession,
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    rows = await spots_services.list_saved_spots(session, user_id=user_id, limit=limit)
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


@router.post(
    "/users/me/saved/{content_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Save spot (idempotent: 200 on duplicate)",
)
async def save_spot(
    content_id: str,
    user_id: CurrentUserId,
    session: DbSession,
    response: Response,
) -> dict[str, Any]:
    inserted = await spots_services.save_spot(session, user_id=user_id, content_id=content_id)
    response.status_code = status.HTTP_201_CREATED if inserted else status.HTTP_200_OK
    return ok(SavedSpotToggle(contentId=content_id, saved=True).model_dump())


@router.delete(
    "/users/me/saved/{content_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unsave spot (idempotent)",
)
async def unsave_spot(
    content_id: str,
    user_id: CurrentUserId,
    session: DbSession,
) -> Response:
    await spots_services.unsave_spot(session, user_id=user_id, content_id=content_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
