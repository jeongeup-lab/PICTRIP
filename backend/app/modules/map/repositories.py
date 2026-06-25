"""MAP repositories — DB queries; SQLAlchemy lives here."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import text

from app.core.db import AsyncSession

# Centroids are runtime AVG of visible spot coordinates. mapx=lng, mapy=lat
# (S07 ERD) — do not swap.
_SIDO_CENTROID_SQL = text(
    "SELECT ldong_regn_cd AS code, AVG(mapx) AS cx, AVG(mapy) AS cy "
    "FROM spots WHERE show_flag = 1 AND ldong_regn_cd IS NOT NULL "
    "GROUP BY ldong_regn_cd"
)
_SIGUNGU_CENTROID_SQL = text(
    "SELECT ldong_signgu_cd AS code, AVG(mapx) AS cx, AVG(mapy) AS cy "
    "FROM spots WHERE show_flag = 1 AND ldong_signgu_cd IS NOT NULL "
    "GROUP BY ldong_signgu_cd"
)


async def fetch_regions(session: AsyncSession) -> Sequence[Any]:
    return (
        await session.execute(
            text("SELECT ldong_regn_cd, ldong_regn_nm FROM regions ORDER BY ldong_regn_cd")
        )
    ).all()


async def fetch_sigungus(session: AsyncSession) -> Sequence[Any]:
    return (
        await session.execute(
            text(
                "SELECT ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm FROM sigungus "
                "ORDER BY ldong_signgu_cd"
            )
        )
    ).all()


async def fetch_sido_centroids(session: AsyncSession) -> dict[str, tuple[float, float]]:
    return {
        r.code: (float(r.cx), float(r.cy))
        for r in (await session.execute(_SIDO_CENTROID_SQL)).all()
        if r.cx is not None and r.cy is not None
    }


async def fetch_sigungu_centroids(session: AsyncSession) -> dict[str, tuple[float, float]]:
    return {
        r.code: (float(r.cx), float(r.cy))
        for r in (await session.execute(_SIGUNGU_CENTROID_SQL)).all()
        if r.cx is not None and r.cy is not None
    }
