"""REC routes. Endpoints mirror API spec §9."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.core.db import DbSession
from app.core.kto_images import https_kto_image
from app.core.schemas import ok
from app.modules.recommendations.services import get_today_inspo

router = APIRouter(tags=["REC · recommendation"])


@router.get(
    "/recommendations/today-inspo",
    status_code=status.HTTP_200_OK,
    summary="Today's Inspo — daily-fixed recommended spot",
)
async def today_inspo(session: DbSession) -> dict[str, Any]:
    card = await get_today_inspo(session)
    return ok(
        {
            "contentId": card.content_id,
            "title": card.title,
            "firstImageUrl": https_kto_image(card.first_image_url),
            "addr1": card.addr1,
            "mapx": card.mapx,
            "mapy": card.mapy,
        }
    )
