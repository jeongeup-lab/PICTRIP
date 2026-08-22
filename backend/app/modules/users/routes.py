from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Response, status

from app.core.db import DbSession
from app.core.redis import RedisDep
from app.kto.display import T1_TILE_WIDTH, t1_display_url
from app.modules.spots import services as spots_services
from app.modules.spots.schemas import SpotCard
from app.modules.users import services
from app.modules.users.schemas import (
    AiTransferConsentIn,
    ConsentIn,
    DeleteAccountBody,
    LogoutBody,
    OAuthLoginIn,
    RefreshBody,
    SavedSpotToggle,
)
from app.security.jwt import CurrentUserId
from app.web.envelope import PaginationMeta, ok

router = APIRouter(tags=["USR · user/auth"])


@router.post(
    "/auth/oauth/{provider}",
    status_code=status.HTTP_200_OK,
    summary="OIDC id_token → internal token pair (provider ∈ kakao/apple)",
)
async def oauth_login(
    provider: str,
    body: OAuthLoginIn,
    session: DbSession,
) -> dict[str, Any]:
    pair = await services.authenticate_with_oauth(session, provider, body)
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
    body: DeleteAccountBody | None = None,
) -> Response:
    await services.delete_user_account(
        session,
        redis,
        user_id,
        body.refreshToken if body else None,
        reason=body.reason if body else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/users/me/consents",
    status_code=status.HTTP_200_OK,
    summary="My current consent state (location/terms)",
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
    summary="Upsert my consents (location/terms)",
)
async def put_consents(
    body: ConsentIn,
    user_id: CurrentUserId,
    session: DbSession,
) -> dict[str, Any]:
    consent = await services.put_consents(session, user_id, body)
    return ok(consent.model_dump())


@router.put(
    "/users/me/consents/ai-transfer",
    status_code=status.HTTP_200_OK,
    summary="Record or withdraw consent to send questions abroad (DeepSeek)",
)
async def put_ai_transfer_consent(
    body: AiTransferConsentIn,
    user_id: CurrentUserId,
    session: DbSession,
) -> dict[str, Any]:
    state = await services.put_ai_transfer_consent(session, user_id, body)
    return ok(state.model_dump())


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
            firstImageUrl=t1_display_url(r.first_image_url, r.cpyrht_div_cd, width=T1_TILE_WIDTH),
            addr1=r.addr1,
            mapx=r.mapx,
            mapy=r.mapy,
            category=r.lcls_systm3_nm,
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
