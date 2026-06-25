"""Spot detail with lazy KTO enrichment + 7-day cache (ADR-0007)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import KtoApiUnavailable, ResourceNotFound
from app.core.kto_client import KtoClient, KtoService
from app.core.text import clean_homepage, clean_scalar, verbatim
from app.modules.spots.models import (
    LclsSystmCode,
    Region,
    Sigungu,
    Spot,
    SpotDetail,
    SpotImage,
)
from app.modules.spots.services.cards import load_congestion
from app.modules.spots.services.rows import (
    SpotDetailRow,
    SpotImageRow,
    SpotIntroRow,
)

_DETAIL_TTL = timedelta(days=7)


async def _load_detail_images(session: AsyncSession, content_id: str) -> list[SpotImageRow]:
    rows = (
        await session.execute(
            select(SpotImage.origin_image_url, SpotImage.small_image_url)
            .where(SpotImage.content_id == content_id)
            .order_by(SpotImage.sort_order)
        )
    ).all()
    return [
        SpotImageRow(origin_image_url=r.origin_image_url, small_image_url=r.small_image_url)
        for r in rows
    ]


def _extract_intro(content_type_id: int, intro_data: dict[str, Any] | None) -> SpotIntroRow | None:
    """Map detailIntro2 keys -> SpotIntroRow by contentTypeId; None if no intro_data."""
    if not intro_data:
        return None
    d = intro_data

    def g(*keys: str) -> str | None:
        for k in keys:
            v = clean_scalar(d.get(k))
            if v:
                return v
        return None

    if content_type_id == 39:  # restaurant
        return SpotIntroRow(
            usetime=g("opentimefood"),
            restdate=g("restdatefood"),
            parking=g("parkingfood"),
            infocenter=g("infocenterfood"),
            firstmenu=g("firstmenu"),
            treatmenu=g("treatmenu"),
        )
    return SpotIntroRow(
        usetime=g("usetime", "usetimeculture", "usetimeleports"),
        restdate=g("restdate", "restdateculture", "restdateleports"),
        parking=g("parking", "parkingculture", "parkingleports"),
        infocenter=g("infocenter", "infocenterculture", "infocenterleports"),
    )


def _assemble_detail(
    spot: Any,
    region_name: str | None,
    sigungu_name: str | None,
    congestion: str | None,
    *,
    overview: str | None,
    homepage: str | None,
    tel: str | None,
    images: list[SpotImageRow],
    status: str,
    category: str | None,
    intro: SpotIntroRow | None,
) -> SpotDetailRow:
    return SpotDetailRow(
        content_id=spot.content_id,
        title=spot.title,
        first_image_url=spot.first_image_url,
        addr1=spot.addr1,
        addr2=spot.addr2,
        mapx=float(spot.mapx) if spot.mapx is not None else None,
        mapy=float(spot.mapy) if spot.mapy is not None else None,
        overview=overview,
        homepage=homepage,
        tel=tel,
        region_name=region_name,
        sigungu_name=sigungu_name,
        detail_status=status,
        congestion=congestion,
        images=images,
        category=category,
        intro=intro,
    )


async def _persist_detail(
    session: AsyncSession,
    content_id: str,
    content_type_id: int,
    overview: str | None,
    homepage: str | None,
    tel: str | None,
    images: list[tuple[str, str | None]],
    intro_data: dict[str, Any] | None = None,
) -> None:
    detail_stmt = pg_insert(SpotDetail).values(
        content_id=content_id,
        content_type_id=content_type_id,
        overview=overview,
        homepage=homepage,
        tel=tel,
        intro_data=intro_data,
        cached_at=func.now(),
    )
    detail_stmt = detail_stmt.on_conflict_do_update(
        index_elements=["content_id"],
        set_={
            "content_type_id": content_type_id,
            "overview": overview,
            "homepage": homepage,
            "tel": tel,
            "intro_data": intro_data,
            "cached_at": func.now(),
        },
    )
    await session.execute(detail_stmt)

    for order, (origin, small) in enumerate(images):
        img_stmt = pg_insert(SpotImage).values(
            content_id=content_id,
            origin_image_url=origin,
            small_image_url=small,
            sort_order=order,
        )
        img_stmt = img_stmt.on_conflict_do_update(
            index_elements=["content_id", "sort_order"],
            set_={"origin_image_url": origin, "small_image_url": small},
        )
        await session.execute(img_stmt)

    await session.execute(
        text("DELETE FROM spot_images WHERE content_id = :cid AND sort_order >= :n"),
        {"cid": content_id, "n": len(images)},
    )
    await session.commit()


@dataclass(frozen=True)
class _DetailContext:
    """Spot base row + scalar meta + congestion — the fixed inputs to every
    `_assemble_detail` call, so the orchestrator only varies the KTO-derived fields."""

    spot: Any
    region_name: str | None
    sigungu_name: str | None
    category: str | None
    congestion: str | None

    def assemble(
        self,
        *,
        overview: str | None,
        homepage: str | None,
        tel: str | None,
        images: list[SpotImageRow],
        status: str,
        intro: SpotIntroRow | None,
    ) -> SpotDetailRow:
        return _assemble_detail(
            self.spot,
            self.region_name,
            self.sigungu_name,
            self.congestion,
            overview=overview,
            homepage=homepage,
            tel=tel,
            images=images,
            status=status,
            category=self.category,
            intro=intro,
        )


async def _load_spot_base(session: AsyncSession, content_id: str) -> Any:
    """Load the visible Spot row; raise ResourceNotFound if absent or hidden."""
    spot = (
        await session.execute(
            select(
                Spot.content_id,
                Spot.content_type_id,
                Spot.title,
                Spot.first_image_url,
                Spot.addr1,
                Spot.addr2,
                Spot.mapx,
                Spot.mapy,
                Spot.ldong_regn_cd,
                Spot.ldong_signgu_cd,
                Spot.lcls_systm3,
            ).where(Spot.content_id == content_id, Spot.show_flag == 1)
        )
    ).first()
    if spot is None:
        raise ResourceNotFound(f"Spot '{content_id}' not found.")
    return spot


async def _load_spot_meta(
    session: AsyncSession, spot: Any
) -> tuple[str | None, str | None, str | None]:
    """Resolve (region_name, sigungu_name, category) scalars, skipping lookups
    when the corresponding code is absent."""
    region_name = (
        await session.scalar(
            select(Region.ldong_regn_nm).where(Region.ldong_regn_cd == spot.ldong_regn_cd)
        )
        if spot.ldong_regn_cd
        else None
    )
    sigungu_name = (
        await session.scalar(
            select(Sigungu.ldong_signgu_nm).where(Sigungu.ldong_signgu_cd == spot.ldong_signgu_cd)
        )
        if spot.ldong_signgu_cd
        else None
    )
    category = (
        await session.scalar(
            select(LclsSystmCode.lcls_systm3_nm).where(
                LclsSystmCode.lcls_systm3_cd == spot.lcls_systm3
            )
        )
        if spot.lcls_systm3
        else None
    )
    return region_name, sigungu_name, category


async def _read_cached_detail(
    session: AsyncSession, content_id: str
) -> tuple[Any, list[SpotImageRow]]:
    """Read the cached SpotDetail row (or None) plus its persisted images."""
    detail = (
        await session.execute(
            select(
                SpotDetail.overview,
                SpotDetail.homepage,
                SpotDetail.tel,
                SpotDetail.intro_data,
                SpotDetail.cached_at,
            ).where(SpotDetail.content_id == content_id)
        )
    ).first()
    existing_images = await _load_detail_images(session, content_id)
    return detail, existing_images


async def _fetch_kto_detail(
    kto: KtoClient, content_id: str, content_type_id: int
) -> tuple[str | None, str | None, str | None, list[tuple[str, str | None]], dict[str, Any]]:
    """Fetch + parse the 3 KTO detail endpoints. Propagates KtoApiUnavailable."""
    common_items = await kto.call(KtoService.KOR, "detailCommon2", contentId=content_id)
    image_items = await kto.call(KtoService.KOR, "detailImage2", contentId=content_id, imageYN="Y")
    intro_items = await kto.call(
        KtoService.KOR,
        "detailIntro2",
        contentId=content_id,
        contentTypeId=content_type_id,
    )

    common = common_items[0] if common_items else {}
    overview = verbatim(common.get("overview"))
    homepage = clean_homepage(common.get("homepage"))
    tel = clean_scalar(common.get("tel"))
    images: list[tuple[str, str | None]] = []
    for item in image_items:
        origin = clean_scalar(item.get("originimgurl"))
        if origin is None:
            continue
        images.append((origin, clean_scalar(item.get("smallimageurl"))))

    intro_data: dict[str, Any] = intro_items[0] if intro_items else {}
    return overview, homepage, tel, images, intro_data


async def load_spot_detail(
    session: AsyncSession,
    kto: KtoClient,
    redis: Redis,
    content_id: str,
) -> SpotDetailRow:
    """Spot detail with lazy KTO enrichment (ADR-0007). Commits the read txn
    before any HTTP, then fetches/upserts the 7-day cache outside a txn. On KTO
    failure serves stale or partial — never 502. 404 if absent or show_flag=0.
    redis is injected but unused (reserved for moving the cache off Postgres)."""
    _ = redis
    spot = await _load_spot_base(session, content_id)
    region_name, sigungu_name, category = await _load_spot_meta(session, spot)
    congestion = (await load_congestion(session, [content_id])).get(content_id)
    ctx = _DetailContext(spot, region_name, sigungu_name, category, congestion)

    detail, existing_images = await _read_cached_detail(session, content_id)

    # End read txn before HTTP. commit() (not rollback) keeps rows under savepoint test fixtures.
    await session.commit()

    if detail is not None and (datetime.now(UTC) - detail.cached_at) < _DETAIL_TTL:
        return ctx.assemble(
            overview=detail.overview,
            homepage=detail.homepage,
            tel=detail.tel,
            images=existing_images,
            status="fresh",
            intro=_extract_intro(spot.content_type_id, detail.intro_data),
        )

    try:
        overview, homepage, tel, images, intro_data = await _fetch_kto_detail(
            kto, content_id, spot.content_type_id
        )
    except KtoApiUnavailable:
        if detail is not None:
            return ctx.assemble(
                overview=detail.overview,
                homepage=detail.homepage,
                tel=detail.tel,
                images=existing_images,
                status="stale",
                intro=_extract_intro(spot.content_type_id, detail.intro_data),
            )
        return ctx.assemble(
            overview=None,
            homepage=None,
            tel=None,
            images=[],
            status="unavailable",
            intro=None,
        )

    await _persist_detail(
        session, content_id, spot.content_type_id, overview, homepage, tel, images, intro_data
    )

    return ctx.assemble(
        overview=overview,
        homepage=homepage,
        tel=tel,
        images=[SpotImageRow(origin_image_url=o, small_image_url=s) for o, s in images],
        status="fresh",
        intro=_extract_intro(spot.content_type_id, intro_data),
    )
