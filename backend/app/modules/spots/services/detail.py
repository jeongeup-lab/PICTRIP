from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.kto.client import KtoClient, KtoService
from app.modules.spots.models import (
    LclsSystmCode,
    Region,
    Sigungu,
    Spot,
    SpotDetail,
    SpotImage,
)
from app.modules.spots.services.rows import (
    SpotDetailRow,
    SpotImageRow,
    SpotIntroRow,
)
from app.modules.spots.text import clean_homepage, clean_scalar, verbatim
from app.web.errors import KtoApiUnavailable, ResourceNotFound

logger = get_logger(__name__)

_DETAIL_TTL = timedelta(days=7)

_REDIS_KEY = "spotdetail:v1:{content_id}"
_REDIS_TTL_SECONDS = int(timedelta(hours=1).total_seconds())


@dataclass(frozen=True)
class _DetailCache:
    overview: str | None
    homepage: str | None
    tel: str | None
    intro_data: dict[str, Any] | None
    cached_at: datetime
    images: list[SpotImageRow]


async def _redis_get_detail(redis: Redis, content_id: str) -> _DetailCache | None:
    key = _REDIS_KEY.format(content_id=content_id)
    try:
        raw = await redis.get(key)
    except Exception as exc:
        logger.warning("spot.detail.cache_get_failed", content_id=content_id, error=str(exc))
        return None
    if raw is None:
        return None
    try:
        d = json.loads(raw)
        return _DetailCache(
            overview=d["overview"],
            homepage=d["homepage"],
            tel=d["tel"],
            intro_data=d["intro_data"],
            cached_at=datetime.fromisoformat(d["cached_at"]),
            images=[SpotImageRow(origin_image_url=o, small_image_url=s) for o, s in d["images"]],
        )
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("spot.detail.cache_corrupt", content_id=content_id, error=str(exc))
        return None


async def _redis_set_detail(redis: Redis, content_id: str, cache: _DetailCache) -> None:
    key = _REDIS_KEY.format(content_id=content_id)
    payload = json.dumps(
        {
            "overview": cache.overview,
            "homepage": cache.homepage,
            "tel": cache.tel,
            "intro_data": cache.intro_data,
            "cached_at": cache.cached_at.isoformat(),
            "images": [[i.origin_image_url, i.small_image_url] for i in cache.images],
        }
    )
    try:
        await redis.set(key, payload, ex=_REDIS_TTL_SECONDS)
    except Exception as exc:
        logger.warning("spot.detail.cache_set_failed", content_id=content_id, error=str(exc))


def _is_fresh(cached_at: datetime, modified_time: datetime | None) -> bool:
    return (datetime.now(UTC) - cached_at) < _DETAIL_TTL and (
        modified_time is None or cached_at >= modified_time
    )


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
    if not intro_data:
        return None
    d = intro_data

    def g(*keys: str) -> str | None:
        for k in keys:
            v = clean_scalar(d.get(k))
            if v:
                return v
        return None

    if content_type_id == 39:
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

    if images:
        img_stmt = pg_insert(SpotImage).values(
            [
                {
                    "content_id": content_id,
                    "origin_image_url": origin,
                    "small_image_url": small,
                    "sort_order": order,
                }
                for order, (origin, small) in enumerate(images)
            ]
        )
        img_stmt = img_stmt.on_conflict_do_update(
            index_elements=["content_id", "sort_order"],
            set_={
                "origin_image_url": img_stmt.excluded.origin_image_url,
                "small_image_url": img_stmt.excluded.small_image_url,
            },
        )
        await session.execute(img_stmt)

    await session.execute(
        text("DELETE FROM spot_images WHERE content_id = :cid AND sort_order >= :n"),
        {"cid": content_id, "n": len(images)},
    )
    await session.commit()


@dataclass(frozen=True)
class _DetailContext:
    spot: Any
    region_name: str | None
    sigungu_name: str | None
    category: str | None

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
            overview=overview,
            homepage=homepage,
            tel=tel,
            images=images,
            status=status,
            category=self.category,
            intro=intro,
        )


async def _load_spot_context(session: AsyncSession, content_id: str) -> Any:
    row = (
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
                Spot.modified_time,
                Region.ldong_regn_nm.label("region_name"),
                Sigungu.ldong_signgu_nm.label("sigungu_name"),
                LclsSystmCode.lcls_systm3_nm.label("category"),
            )
            .select_from(Spot)
            .outerjoin(Region, Region.ldong_regn_cd == Spot.ldong_regn_cd)
            .outerjoin(Sigungu, Sigungu.ldong_signgu_cd == Spot.ldong_signgu_cd)
            .outerjoin(LclsSystmCode, LclsSystmCode.lcls_systm3_cd == Spot.lcls_systm3)
            .where(Spot.content_id == content_id, Spot.show_flag == 1)
        )
    ).first()
    if row is None:
        raise ResourceNotFound(f"Spot '{content_id}' not found.")
    return row


async def _read_cached_detail(
    session: AsyncSession, content_id: str
) -> tuple[Any, list[SpotImageRow]]:
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


_KTO_DETAIL_BUDGET = 8.0


async def _fetch_kto_detail(
    kto: KtoClient, content_id: str, content_type_id: int
) -> tuple[str | None, str | None, str | None, list[tuple[str, str | None]], dict[str, Any]]:
    try:
        common_items, image_items, intro_items = await asyncio.wait_for(
            asyncio.gather(
                kto.call(KtoService.KOR, "detailCommon2", contentId=content_id),
                kto.call(KtoService.KOR, "detailImage2", contentId=content_id, imageYN="Y"),
                kto.call(
                    KtoService.KOR,
                    "detailIntro2",
                    contentId=content_id,
                    contentTypeId=content_type_id,
                ),
            ),
            timeout=_KTO_DETAIL_BUDGET,
        )
    except TimeoutError as exc:
        raise KtoApiUnavailable("KTO detail fetch exceeded budget") from exc

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
    spot = await _load_spot_context(session, content_id)
    ctx = _DetailContext(spot, spot.region_name, spot.sigungu_name, spot.category)

    cache = await _redis_get_detail(redis, content_id)
    redis_fresh = cache is not None and _is_fresh(cache.cached_at, spot.modified_time)
    if not redis_fresh:
        detail, existing_images = await _read_cached_detail(session, content_id)
        if detail is not None:
            cache = _DetailCache(
                overview=detail.overview,
                homepage=detail.homepage,
                tel=detail.tel,
                intro_data=detail.intro_data,
                cached_at=detail.cached_at,
                images=existing_images,
            )

    await session.commit()

    if cache is not None and _is_fresh(cache.cached_at, spot.modified_time):
        if not redis_fresh:
            await _redis_set_detail(redis, content_id, cache)
        return ctx.assemble(
            overview=cache.overview,
            homepage=cache.homepage,
            tel=cache.tel,
            images=cache.images,
            status="fresh",
            intro=_extract_intro(spot.content_type_id, cache.intro_data),
        )

    try:
        overview, homepage, tel, images, intro_data = await _fetch_kto_detail(
            kto, content_id, spot.content_type_id
        )
    except KtoApiUnavailable:
        if cache is not None:
            return ctx.assemble(
                overview=cache.overview,
                homepage=cache.homepage,
                tel=cache.tel,
                images=cache.images,
                status="stale",
                intro=_extract_intro(spot.content_type_id, cache.intro_data),
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
    image_rows = [SpotImageRow(origin_image_url=o, small_image_url=s) for o, s in images]
    await _redis_set_detail(
        redis,
        content_id,
        _DetailCache(
            overview=overview,
            homepage=homepage,
            tel=tel,
            intro_data=intro_data,
            cached_at=datetime.now(UTC),
            images=image_rows,
        ),
    )

    return ctx.assemble(
        overview=overview,
        homepage=homepage,
        tel=tel,
        images=image_rows,
        status="fresh",
        intro=_extract_intro(spot.content_type_id, intro_data),
    )
