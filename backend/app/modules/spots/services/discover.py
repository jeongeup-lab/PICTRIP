"""Discover query for the discovery chat — SPT owns the Spot filters; chat consumes rows.

The 스무고개 board narrows a candidate set by stacking structured filters
(region/category SQL), a quiet signal (spot_concentration), and free keywords
(title/overview ILIKE). ``pool_total`` is the unconstrained discoverable count
used as the board's "N곳에서" scale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Integer, and_, case, false, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.modules.spots.models import (
    LclsSystmCode,
    Region,
    Sigungu,
    Spot,
    SpotConcentration,
    SpotDetail,
)
from app.modules.spots.services.nearby import (
    NearbyCategory,
    all_categories_predicate,
    category_predicate,
)

QUIET_RATE_MAX = 34.0


@dataclass(frozen=True)
class DiscoverFilters:
    region_cd: str | None = None
    sigungu_cd: str | None = None
    categories: tuple[NearbyCategory, ...] = ()
    exclude_categories: tuple[NearbyCategory, ...] = ()
    keywords: tuple[str, ...] = field(default_factory=tuple)
    quiet: bool = False


@dataclass(frozen=True)
class DiscoverRow:
    content_id: str
    title: str
    first_image_url: str
    category: str | None
    region_label: str
    overview_head: str | None
    quiet: bool | None


def _escape_like(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _base_conditions() -> list[ColumnElement[bool]]:
    return [
        Spot.show_flag == 1,
        Spot.first_image_url.isnot(None),
        Spot.first_image_url != "",
    ]


def _conditions(filters: DiscoverFilters) -> list[ColumnElement[bool]]:
    conds = _base_conditions()
    if filters.categories:
        conds.append(or_(*(category_predicate(c) for c in filters.categories)))
    else:
        conds.append(all_categories_predicate())
    for c in filters.exclude_categories:
        # coalesce NULL -> false: a spot with NULL category columns is NOT in the
        # category, so a bare not_(predicate) (which is NULL on NULLs, failing the
        # WHERE) must not drop it.
        conds.append(not_(func.coalesce(category_predicate(c), false())))
    if filters.region_cd:
        conds.append(Spot.ldong_regn_cd == filters.region_cd)
    if filters.sigungu_cd:
        conds.append(Spot.ldong_signgu_cd == filters.sigungu_cd)
    if filters.keywords:
        kw_clauses: list[ColumnElement[bool]] = []
        for kw in filters.keywords:
            pat = f"%{_escape_like(kw)}%"
            kw_clauses.append(Spot.title.ilike(pat, escape="\\"))
            kw_clauses.append(
                and_(SpotDetail.overview.isnot(None), SpotDetail.overview.ilike(pat, escape="\\"))
            )
        conds.append(or_(*kw_clauses))
    return conds


async def pool_total(session: AsyncSession) -> int:
    """Unconstrained discoverable count (the 스무고개 board's 'N곳에서' scale)."""
    stmt = (
        select(func.count())
        .select_from(Spot)
        .where(*_base_conditions(), all_categories_predicate())
    )
    return int((await session.execute(stmt)).scalar_one())


async def discover_spots(
    session: AsyncSession,
    *,
    filters: DiscoverFilters,
    limit: int,
) -> tuple[list[DiscoverRow], int]:
    conds = _conditions(filters)
    base = (
        select(Spot.content_id)
        .outerjoin(SpotDetail, SpotDetail.content_id == Spot.content_id)
        .where(*conds)
    )
    total = int(
        (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    )

    has_overview = case((SpotDetail.overview.isnot(None), 1), else_=0).cast(Integer)
    primary_order: ColumnElement[Any]
    if filters.quiet:
        primary_order = SpotConcentration.concentration_rate.asc().nulls_last()
    else:
        primary_order = has_overview.desc()
    stmt = (
        select(
            Spot.content_id,
            Spot.title,
            Spot.first_image_url,
            LclsSystmCode.lcls_systm3_nm.label("category"),
            SpotDetail.overview.label("overview"),
            SpotConcentration.concentration_rate.label("rate"),
            Region.ldong_regn_nm.label("region_nm"),
            Sigungu.ldong_signgu_nm.label("signgu_nm"),
        )
        .outerjoin(SpotDetail, SpotDetail.content_id == Spot.content_id)
        .outerjoin(LclsSystmCode, LclsSystmCode.lcls_systm3_cd == Spot.lcls_systm3)
        .outerjoin(SpotConcentration, SpotConcentration.content_id == Spot.content_id)
        .outerjoin(Region, Region.ldong_regn_cd == Spot.ldong_regn_cd)
        .outerjoin(Sigungu, Sigungu.ldong_signgu_cd == Spot.ldong_signgu_cd)
        .where(*conds)
        .order_by(primary_order, Spot.content_id.asc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    out: list[DiscoverRow] = []
    for r in rows:
        head = r.overview.split("\n")[0][:80] if r.overview else None
        quiet = None if r.rate is None else float(r.rate) <= QUIET_RATE_MAX
        label = " ".join(p for p in (r.region_nm, r.signgu_nm) if p)
        out.append(
            DiscoverRow(
                content_id=r.content_id,
                title=r.title or "",
                first_image_url=r.first_image_url,
                category=r.category,
                region_label=label,
                overview_head=head,
                quiet=quiet,
            )
        )
    return out, total


async def resolve_region(session: AsyncSession, name: str) -> tuple[str, str | None, str] | None:
    """Resolve a free-text region name to (region_cd, sigungu_cd|None, label)."""
    q = name.strip()
    if len(q) < 2:
        return None
    sig = (
        await session.execute(
            select(Sigungu.ldong_signgu_cd, Sigungu.ldong_regn_cd, Sigungu.ldong_signgu_nm)
            .where(Sigungu.ldong_signgu_nm.ilike(f"{_escape_like(q)}%", escape="\\"))
            .order_by(Sigungu.ldong_signgu_cd)
            .limit(1)
        )
    ).first()
    if sig:
        return (sig.ldong_regn_cd, sig.ldong_signgu_cd, sig.ldong_signgu_nm)
    reg = (
        await session.execute(
            select(Region.ldong_regn_cd, Region.ldong_regn_nm)
            .where(Region.ldong_regn_nm.ilike(f"%{_escape_like(q)}%", escape="\\"))
            .order_by(Region.ldong_regn_cd)
            .limit(1)
        )
    ).first()
    if reg:
        return (reg.ldong_regn_cd, None, reg.ldong_regn_nm)
    return None
