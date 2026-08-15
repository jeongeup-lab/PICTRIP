from __future__ import annotations

from typing import cast, get_args

from app.core.db import AsyncSession
from app.kto.display import T1_TILE_WIDTH, t1_display_url
from app.modules.agent import repositories
from app.modules.agent.schemas import Mood, MoodImage, MoodImagesResponse

ALL_MOODS: tuple[Mood, ...] = get_args(Mood)


async def mood_images(session: AsyncSession) -> MoodImagesResponse:
    rows = await repositories.load_mood_images(session, list(ALL_MOODS))
    images = [
        MoodImage(code=cast(Mood, row.code), imageUrl=url)
        for row, url in (
            (row, t1_display_url(row.image_url, row.cpyrht_div_cd, width=T1_TILE_WIDTH))
            for row in rows
        )
        if url
    ]
    return MoodImagesResponse(images=images)
