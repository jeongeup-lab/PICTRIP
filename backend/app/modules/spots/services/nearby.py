"""내 주변(nearby) SPT 서비스 — bbox+haversine 거리 쿼리 + 카테고리 taxonomy.

`Spot.lcls_systm{1,2,3}` 컬럼에 묶인 도메인 지식과 `spots` 테이블에 대한
SQLAlchemy 쿼리는 SPT가 소유한다(backend/CLAUDE.md: select against Spot은 SPT에만).
MAP은 이 함수가 돌려준 행에 crowd(Redis)만 머지한다 — `app.modules.map.services` 참조.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.modules.spots.models import Spot, SpotDetail

_MAX_NUM_OF_ROWS = 50
_EARTH_RADIUS_M = 6_371_000.0
_VE_EXCLUDE = ("VE06", "VE07", "VE08", "VE09", "VE10", "VE11")


class NearbyCategory(StrEnum):
    attraction = "attraction"
    food = "food"
    cafe = "cafe"
    leisure = "leisure"
    shopping = "shopping"


@dataclass
class NearbySpotRow:
    content_id: str
    title: str
    first_image_url: str | None
    first_image2_url: str | None
    addr1: str | None
    mapx: float | None
    mapy: float | None
    dist: float | None
    category: str | None = None  # 파생 칩 코드 (derive_category)
    # KTO overview(verbatim) — spot_details에만 존재하고 상세 조회 시 lazy 캐시되므로
    # 대부분 None이다. 카드 설명 줄은 있을 때만 노출(요약·가공 금지, 클라가 시각 truncate).
    overview: str | None = None


def category_predicate(cat: NearbyCategory) -> ColumnElement[bool]:
    """SSOT 규칙 → SQLAlchemy boolean 표현식 (nearby 쿼리 WHERE에 AND)."""
    if cat is NearbyCategory.attraction:
        return or_(
            Spot.lcls_systm1.in_(("HS", "NA", "EX")),
            and_(
                Spot.lcls_systm1 == "VE",
                or_(Spot.lcls_systm2.is_(None), Spot.lcls_systm2.notin_(_VE_EXCLUDE)),
            ),
        )
    if cat is NearbyCategory.food:
        return and_(
            Spot.lcls_systm2.in_(("FD01", "FD02", "FD03")),
            or_(Spot.lcls_systm3.is_(None), Spot.lcls_systm3 != "FD030100"),
        )
    if cat is NearbyCategory.cafe:
        return or_(Spot.lcls_systm2 == "FD05", Spot.lcls_systm3 == "FD030100")
    if cat is NearbyCategory.leisure:
        return Spot.lcls_systm1 == "LS"
    # shopping
    return and_(
        Spot.lcls_systm1 == "SH",
        or_(Spot.lcls_systm2.is_(None), Spot.lcls_systm2 != "SH04"),
    )


def derive_category(l1: str | None, l2: str | None, l3: str | None) -> str | None:
    """행의 lcls 값 → 칩 코드(표시용). 우선순위: cafe→food→attraction→leisure→shopping.

    (cafe를 food보다 먼저: FD030100(제과)이 food 제외항목이자 cafe 포함항목.)
    """
    if l2 == "FD05" or l3 == "FD030100":
        return "cafe"
    if l2 in ("FD01", "FD02", "FD03") and l3 != "FD030100":
        return "food"
    if l1 in ("HS", "NA", "EX") or (l1 == "VE" and l2 not in _VE_EXCLUDE):
        return "attraction"
    if l1 == "LS":
        return "leisure"
    if l1 == "SH" and l2 != "SH04":
        return "shopping"
    return None


async def find_nearby_spots(
    session: AsyncSession,
    *,
    lat: float,
    lng: float,
    radius: int,
    category: NearbyCategory | None,
) -> list[NearbySpotRow]:
    """반경 `radius` m 내 활성·이미지 보유 스팟을 거리순으로(crowd 없음 — MAP이 머지).

    base = show_flag=1 AND first_image_url IS NOT NULL (spec §3.1).
    bbox 프리필터(idx_spots_active_location) → Haversine 거리 → 카테고리 → 거리순 LIMIT.

    category=None('전체')은 무필터가 아니라 정의된 5개 카테고리의 union으로 제한한다 —
    숙박 외 미분류·면세점 등 어느 칩에도 안 잡히는(derive_category=None) 스팟은 제외.
    """
    # 1) bounding box (도 단위). 고위도 cos 0 방지.
    dlat = radius / 111_320.0
    dlng = radius / (111_320.0 * max(math.cos(math.radians(lat)), 0.01))

    # 2) Haversine 거리(m). mapy=lat, mapx=lng. acos 도메인 클램프.
    cos_term = func.cos(func.radians(lat)) * func.cos(func.radians(Spot.mapy)) * func.cos(
        func.radians(Spot.mapx) - func.radians(lng)
    ) + func.sin(func.radians(lat)) * func.sin(func.radians(Spot.mapy))
    dist = (_EARTH_RADIUS_M * func.acos(func.least(1.0, func.greatest(-1.0, cos_term)))).label(
        "dist"
    )

    inner = (
        select(
            Spot.content_id.label("content_id"),
            Spot.title.label("title"),
            Spot.first_image_url.label("first_image_url"),
            Spot.first_image2_url.label("first_image2_url"),
            Spot.addr1.label("addr1"),
            Spot.mapx.label("mapx"),
            Spot.mapy.label("mapy"),
            Spot.lcls_systm1.label("l1"),
            Spot.lcls_systm2.label("l2"),
            Spot.lcls_systm3.label("l3"),
            SpotDetail.overview.label("overview"),
            dist,
        )
        .outerjoin(SpotDetail, SpotDetail.content_id == Spot.content_id)
        .where(
            Spot.show_flag == 1,
            Spot.first_image_url.isnot(None),
            Spot.mapx.isnot(None),
            Spot.mapy.isnot(None),
            Spot.mapy.between(lat - dlat, lat + dlat),
            Spot.mapx.between(lng - dlng, lng + dlng),
        )
    )
    if category is not None:
        inner = inner.where(category_predicate(category))
    else:
        # '전체' = 정의된 5개 카테고리 union. 미분류 스팟은 노출 안 함.
        inner = inner.where(or_(*(category_predicate(c) for c in NearbyCategory)))

    sub = inner.subquery()
    stmt = select(sub).where(sub.c.dist <= radius).order_by(sub.c.dist).limit(_MAX_NUM_OF_ROWS)

    result = await session.execute(stmt)
    rows: list[NearbySpotRow] = []
    for r in result:
        rows.append(
            NearbySpotRow(
                content_id=r.content_id,
                title=r.title or "",
                first_image_url=r.first_image_url,
                first_image2_url=r.first_image2_url,
                addr1=r.addr1,
                mapx=float(r.mapx) if r.mapx is not None else None,
                mapy=float(r.mapy) if r.mapy is not None else None,
                dist=float(r.dist) if r.dist is not None else None,
                category=derive_category(r.l1, r.l2, r.l3),
                overview=r.overview,
            )
        )
    return rows
