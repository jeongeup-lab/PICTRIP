from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.plan.models import Plan
from app.modules.spots.services import attraction_category_sql, derive_category


@dataclass
class PhotoMatchRow:
    content_id: str
    title: str
    category: str | None
    addr1: str | None
    lat: float | None
    lng: float | None
    image_url: str | None
    distance: float


def _photo_match_sql() -> str:
    gate = attraction_category_sql()
    return f"""
WITH q AS (SELECT CAST(:vec AS halfvec(512)) AS v),
single AS (
    SELECT se.content_id, (se.embedding <=> (SELECT v FROM q))::float AS distance
    FROM spot_embeddings se
    JOIN spots ON spots.content_id = se.content_id
              AND spots.first_image_url = se.image_url
              AND spots.show_flag = 1
              AND spots.first_image_url IS NOT NULL
              AND spots.first_image_url <> ''
              AND ({gate})
    ORDER BY se.embedding <=> (SELECT v FROM q)
    LIMIT :lim
),
gallery AS (
    SELECT ge.content_id, (ge.embedding <=> (SELECT v FROM q))::float AS distance
    FROM spot_embeddings_gallery ge
    JOIN spots ON spots.content_id = ge.content_id
              AND spots.show_flag = 1
              AND spots.first_image_url IS NOT NULL
              AND spots.first_image_url <> ''
              AND ({gate})
    ORDER BY ge.embedding <=> (SELECT v FROM q)
    LIMIT :lim
)
SELECT s.content_id, s.title, s.addr1, s.mapx, s.mapy, s.first_image_url,
       s.lcls_systm1, s.lcls_systm2, s.lcls_systm3, best.distance
FROM (
    SELECT DISTINCT ON (content_id) content_id, distance
    FROM (SELECT * FROM single UNION ALL SELECT * FROM gallery) candidates
    ORDER BY content_id, distance
) best
JOIN spots s ON s.content_id = best.content_id
ORDER BY best.distance
LIMIT :lim
"""


async def match_spots_by_vector(
    session: AsyncSession, vector: list[float], *, limit: int
) -> list[PhotoMatchRow]:
    literal = "[" + ",".join(f"{v:.6f}" for v in vector) + "]"
    result = await session.execute(text(_photo_match_sql()), {"vec": literal, "lim": limit})
    rows: list[PhotoMatchRow] = []
    for r in result:
        rows.append(
            PhotoMatchRow(
                content_id=r.content_id,
                title=r.title,
                category=derive_category(r.lcls_systm1, r.lcls_systm2, r.lcls_systm3),
                addr1=r.addr1,
                lat=r.mapy,
                lng=r.mapx,
                image_url=r.first_image_url,
                distance=float(r.distance),
            )
        )
    return rows


async def insert_plan(
    session: AsyncSession,
    *,
    plan_id: uuid.UUID,
    thread_id: str,
    user_id: int | None,
    payload: dict[str, Any],
) -> Plan:
    plan = Plan(id=plan_id, thread_id=thread_id, user_id=user_id, payload=payload)
    session.add(plan)
    await session.commit()
    return plan


async def get_plan(session: AsyncSession, plan_id: uuid.UUID) -> Plan | None:
    result: Plan | None = await session.scalar(select(Plan).where(Plan.id == plan_id))
    return result
