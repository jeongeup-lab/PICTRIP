from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text

from app.core.db import AsyncSession
from app.modules.plan.models import Plan
from app.modules.spots.services import attraction_category_sql


def _new_public_id() -> str:
    return secrets.token_urlsafe(12)


async def create_plan(
    session: AsyncSession,
    *,
    source_kind: str,
    source_url: str | None,
    source_title: str | None,
    payload: dict[str, Any],
) -> Plan:
    plan = Plan(
        public_id=_new_public_id(),
        source_kind=source_kind,
        source_url=source_url,
        source_title=source_title,
        payload=payload,
    )
    session.add(plan)
    await session.flush()
    return plan


async def get_plan(session: AsyncSession, public_id: str) -> Plan | None:
    result = await session.execute(select(Plan).where(Plan.public_id == public_id))
    return result.scalar_one_or_none()


async def get_plan_payload(session: AsyncSession, public_id: str) -> dict[str, Any] | None:
    plan = await get_plan(session, public_id)
    return None if plan is None else plan.payload


async def set_plan_payload(session: AsyncSession, public_id: str, payload: dict[str, Any]) -> None:
    plan = await get_plan(session, public_id)
    if plan is not None:
        plan.payload = payload
        await session.flush()


@dataclass(frozen=True)
class VectorMatchRow:
    content_id: str
    title: str
    category: str | None
    addr1: str | None
    lat: float | None
    lng: float | None
    image_url: str | None
    distance: float


_VECTOR_MATCH_SQL = f"""
SELECT spots.content_id,
       spots.title,
       c.lcls_systm3_nm AS category,
       spots.addr1,
       spots.mapy AS lat,
       spots.mapx AS lng,
       spots.first_image_url AS image_url,
       (se.embedding <=> CAST(:vec AS halfvec(512)))::float AS distance
FROM spot_embeddings se
JOIN spots ON spots.content_id = se.content_id
          AND spots.show_flag = 1
          AND spots.first_image_url IS NOT NULL
          AND spots.first_image_url <> ''
          AND ({attraction_category_sql()})
LEFT JOIN lcls_systm_codes c ON c.lcls_systm3_cd = spots.lcls_systm3
ORDER BY se.embedding <=> CAST(:vec AS halfvec(512))
LIMIT :lim
"""


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


async def match_spots_by_vector(
    session: AsyncSession, vector: list[float], *, limit: int
) -> list[VectorMatchRow]:
    result = await session.execute(
        text(_VECTOR_MATCH_SQL), {"vec": _vector_literal(vector), "lim": limit}
    )
    return [
        VectorMatchRow(
            content_id=row.content_id,
            title=row.title or "",
            category=row.category,
            addr1=row.addr1,
            lat=float(row.lat) if row.lat is not None else None,
            lng=float(row.lng) if row.lng is not None else None,
            image_url=row.image_url,
            distance=float(row.distance),
        )
        for row in result
    ]


@dataclass(frozen=True)
class SpotBrief:
    content_id: str
    title: str
    category: str | None
    addr1: str | None
    lat: float | None
    lng: float | None
    image_url: str | None


_SPOT_BRIEF_SQL = """
SELECT s.content_id,
       s.title,
       c.lcls_systm3_nm AS category,
       s.addr1,
       s.mapy AS lat,
       s.mapx AS lng,
       s.first_image_url AS image_url
FROM spots s
LEFT JOIN lcls_systm_codes c ON c.lcls_systm3_cd = s.lcls_systm3
WHERE s.content_id = :cid AND s.show_flag = 1
"""


async def get_spot_brief(session: AsyncSession, content_id: str) -> SpotBrief | None:
    row = (await session.execute(text(_SPOT_BRIEF_SQL), {"cid": content_id})).first()
    if row is None:
        return None
    return SpotBrief(
        content_id=row.content_id,
        title=row.title or "",
        category=row.category,
        addr1=row.addr1,
        lat=float(row.lat) if row.lat is not None else None,
        lng=float(row.lng) if row.lng is not None else None,
        image_url=row.image_url,
    )
