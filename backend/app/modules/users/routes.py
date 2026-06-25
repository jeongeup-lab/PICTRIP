"""USR routes (API spec §5)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Response, status

from app.core.auth import CurrentUserId
from app.core.db import DbSession
from app.core.redis import RedisDep
from app.core.schemas import PaginationMeta, ok
from app.modules.spots import services as spots_services
from app.modules.spots.schemas import SpotCard
from app.modules.users import services
from app.modules.users.schemas import (
    ConsentIn,
    EmailLoginIn,
    EmailSignupIn,
    LogoutBody,
    OAuthLoginIn,
    RefreshBody,
    SavedSpotToggle,
)

router = APIRouter(tags=["USR · user/auth"])


@router.post(
    "/auth/oauth/{provider}",
    status_code=status.HTTP_200_OK,
    summary="OIDC id_token → internal token pair (provider ∈ kakao/google/apple)",
)
async def oauth_login(
    provider: str,
    body: OAuthLoginIn,
    session: DbSession,
) -> dict[str, Any]:
    pair = await services.authenticate_with_oauth(session, provider, body)
    return ok(pair.model_dump())


@router.post(
    "/auth/email/signup",
    status_code=status.HTTP_201_CREATED,
    summary="Email/password signup → internal token pair",
)
async def email_signup(body: EmailSignupIn, session: DbSession) -> dict[str, Any]:
    pair = await services.signup_with_email(session, body)
    return ok(pair.model_dump())


@router.post(
    "/auth/email/login",
    status_code=status.HTTP_200_OK,
    summary="Email/password login → internal token pair",
)
async def email_login(body: EmailLoginIn, session: DbSession) -> dict[str, Any]:
    pair = await services.login_with_email(session, body)
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


@router.get(
    "/users/me/consents",
    status_code=status.HTTP_200_OK,
    summary="My current consent state (location/photo/terms)",
)
async def get_consents(
    user_id: CurrentUserId,
    session: DbSession,
) -> dict[str, Any]:
    state = await services.get_consents(session, user_id)
    return ok(state.model_dump())


@router.put(
    "/users/me/consents",
    status_code=status.HTTP_200_OK,
    summary="Upsert my consents (location/photo/terms)",
)
async def put_consents(
    body: ConsentIn,
    user_id: CurrentUserId,
    session: DbSession,
) -> dict[str, Any]:
    consent = await services.put_consents(session, user_id, body)
    return ok(consent.model_dump())


@router.get(
    "/users/me/saved",
    status_code=status.HTTP_200_OK,
    summary="My saved spots list (spot card)",
)
async def list_saved(
    user_id: CurrentUserId,
    session: DbSession,
    limit: int = Query(default=24, ge=1, le=60),
    cursor: str | None = Query(default=None),
) -> dict[str, Any]:
    rows, next_cursor, has_more = await spots_services.list_saved_spots(
        session, user_id=user_id, limit=limit, cursor=cursor
    )
    cards = [
        SpotCard(
            contentId=r.content_id,
            title=r.title,
            firstImageUrl=r.first_image_url,
            addr1=r.addr1,
            mapx=r.mapx,
            mapy=r.mapy,
            category=r.lcls_systm3_nm,
            congestion=r.congestion,
        )
        for r in rows
    ]
    return ok(
        [c.model_dump() for c in cards],
        pagination=PaginationMeta(
            nextCursor=next_cursor,
            hasMore=has_more,
            count=len(cards),
        ),
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
