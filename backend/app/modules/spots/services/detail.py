from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_factory
from app.core.logging import get_logger
from app.kto.client import KtoClient, KtoService
from app.kto.text import clean_homepage, clean_scalar, verbatim
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
from app.web.errors import KtoApiUnavailable, ResourceNotFound

logger = get_logger(__name__)

_DETAIL_TTL = timedelta(days=90)

_REDIS_KEY = "spotdetail:v2:{content_id}"
_REDIS_TTL_SECONDS = int(timedelta(hours=1).total_seconds())
_REFRESH_LOCK_KEY = "spotdetail:refresh:v1:{content_id}"
_REFRESH_LOCK_TTL_SECONDS = 20
_REFRESH_BACKOFF_KEY = "spotdetail:refresh-backoff:v1:{content_id}"
_REFRESH_BACKOFF_TTL_SECONDS = 60
_NEVER_CACHED = datetime(1970, 1, 1, tzinfo=UTC)
_RELEASE_REFRESH_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
end
return 0
"""


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
            images=[
                SpotImageRow(origin_image_url=o, small_image_url=s, cpyrht_div_cd=c)
                for o, s, c in d["images"]
            ],
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
            "images": [
                [i.origin_image_url, i.small_image_url, i.cpyrht_div_cd] for i in cache.images
            ],
        }
    )
    try:
        await redis.set(key, payload, ex=_REDIS_TTL_SECONDS)
    except Exception as exc:
        logger.warning("spot.detail.cache_set_failed", content_id=content_id, error=str(exc))


async def invalidate_spot_detail_cache(redis: Redis, content_id: str) -> None:
    try:
        await redis.delete(_REDIS_KEY.format(content_id=content_id))
    except Exception as exc:
        logger.warning("spot.detail.cache_del_failed", content_id=content_id, error=str(exc))


async def _refresh_in_backoff(redis: Redis, content_id: str) -> bool:
    try:
        return bool(await redis.get(_REFRESH_BACKOFF_KEY.format(content_id=content_id)))
    except Exception as exc:
        logger.warning("spot.detail.backoff_get_failed", content_id=content_id, error=str(exc))
        return False


async def _set_refresh_backoff(redis: Redis, content_id: str) -> None:
    try:
        await redis.set(
            _REFRESH_BACKOFF_KEY.format(content_id=content_id),
            "1",
            ex=_REFRESH_BACKOFF_TTL_SECONDS,
        )
    except Exception as exc:
        logger.warning("spot.detail.backoff_set_failed", content_id=content_id, error=str(exc))


async def _acquire_refresh_lock(redis: Redis, content_id: str) -> tuple[bool, str | None]:
    token = secrets.token_hex(16)
    try:
        acquired = await redis.set(
            _REFRESH_LOCK_KEY.format(content_id=content_id),
            token,
            ex=_REFRESH_LOCK_TTL_SECONDS,
            nx=True,
        )
    except Exception as exc:
        logger.warning("spot.detail.refresh_lock_failed", content_id=content_id, error=str(exc))
        return True, None
    return bool(acquired), token if acquired else None


async def _release_refresh_lock(redis: Redis, content_id: str, token: str | None) -> None:
    if token is None:
        return
    try:
        await cast(
            Awaitable[Any],
            redis.eval(
                _RELEASE_REFRESH_LOCK_SCRIPT,
                1,
                _REFRESH_LOCK_KEY.format(content_id=content_id),
                token,
            ),
        )
    except Exception as exc:
        logger.warning("spot.detail.refresh_unlock_failed", content_id=content_id, error=str(exc))


def is_detail_fresh(cached_at: datetime, modified_time: datetime | None) -> bool:
    return (datetime.now(UTC) - cached_at) < _DETAIL_TTL and (
        modified_time is None or cached_at >= modified_time
    )


def _is_fresh(cached_at: datetime, modified_time: datetime | None) -> bool:
    return is_detail_fresh(cached_at, modified_time)


async def _load_detail_images(session: AsyncSession, content_id: str) -> list[SpotImageRow]:
    rows = (
        await session.execute(
            select(
                SpotImage.origin_image_url,
                SpotImage.small_image_url,
                SpotImage.cpyrht_div_cd,
            )
            .where(SpotImage.content_id == content_id)
            .order_by(SpotImage.sort_order)
        )
    ).all()
    return [
        SpotImageRow(
            origin_image_url=r.origin_image_url,
            small_image_url=r.small_image_url,
            cpyrht_div_cd=r.cpyrht_div_cd,
        )
        for r in rows
    ]


async def replace_spot_images(
    session: AsyncSession, content_id: str, images: list[SpotImageRow]
) -> None:
    if images:
        img_stmt = pg_insert(SpotImage).values(
            [
                {
                    "content_id": content_id,
                    "origin_image_url": image.origin_image_url,
                    "small_image_url": image.small_image_url,
                    "cpyrht_div_cd": image.cpyrht_div_cd,
                    "sort_order": order,
                }
                for order, image in enumerate(images)
            ]
        )
        img_stmt = img_stmt.on_conflict_do_update(
            index_elements=["content_id", "sort_order"],
            set_={
                "origin_image_url": img_stmt.excluded.origin_image_url,
                "small_image_url": img_stmt.excluded.small_image_url,
                "cpyrht_div_cd": img_stmt.excluded.cpyrht_div_cd,
            },
        )
        await session.execute(img_stmt)

    await session.execute(
        text("DELETE FROM spot_images WHERE content_id = :cid AND sort_order >= :n"),
        {"cid": content_id, "n": len(images)},
    )


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
            usefee=None,
            restdate=g("restdatefood"),
            parking=g("parkingfood"),
            infocenter=g("infocenterfood"),
            firstmenu=g("firstmenu"),
            treatmenu=g("treatmenu"),
        )
    return SpotIntroRow(
        usetime=g("usetime", "usetimeculture", "usetimeleports"),
        usefee=g("usefee", "usefeeculture", "usefeeleports"),
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
        cpyrht_div_cd=spot.cpyrht_div_cd,
    )


async def _persist_detail(
    session: AsyncSession,
    content_id: str,
    content_type_id: int,
    fetched: _KtoDetail,
) -> None:
    """실패한 오퍼레이션의 칸은 건드리지 않는다 — 쿼터 초과가 캐시를 NULL 로 지우면 안 된다."""
    updated: dict[str, Any] = {"content_type_id": content_type_id}
    if fetched.common_ok:
        updated |= {
            "overview": fetched.overview,
            "homepage": fetched.homepage,
            "tel": fetched.tel,
        }
    if fetched.intro_ok:
        updated["intro_data"] = fetched.intro_data
    if fetched.complete:
        updated["cached_at"] = func.now()

    detail_stmt = pg_insert(SpotDetail).values(
        content_id=content_id,
        content_type_id=content_type_id,
        overview=fetched.overview,
        homepage=fetched.homepage,
        tel=fetched.tel,
        intro_data=fetched.intro_data,
        cached_at=func.now() if fetched.complete else _NEVER_CACHED,
    )
    detail_stmt = detail_stmt.on_conflict_do_update(
        index_elements=["content_id"],
        set_=updated,
    )
    await session.execute(detail_stmt)
    if fetched.images_ok:
        await replace_spot_images(session, content_id, fetched.images)
    await session.commit()


def _merge_with_cache(fetched: _KtoDetail, cache: _DetailCache | None) -> _KtoDetail:
    if cache is None or fetched.complete:
        return fetched
    return _KtoDetail(
        overview=fetched.overview if fetched.common_ok else cache.overview,
        homepage=fetched.homepage if fetched.common_ok else cache.homepage,
        tel=fetched.tel if fetched.common_ok else cache.tel,
        images=fetched.images if fetched.images_ok else cache.images,
        intro_data=fetched.intro_data if fetched.intro_ok else cache.intro_data,
        common_ok=fetched.common_ok,
        images_ok=fetched.images_ok,
        intro_ok=fetched.intro_ok,
    )


async def persist_detail_common(
    session: AsyncSession,
    content_id: str,
    content_type_id: int,
    overview: str | None,
    homepage: str | None,
    tel: str | None,
) -> None:
    columns = {
        "content_type_id": content_type_id,
        "overview": overview,
        "homepage": homepage,
        "tel": tel,
        "cached_at": func.now(),
    }
    stmt = pg_insert(SpotDetail).values(content_id=content_id, **columns)
    stmt = stmt.on_conflict_do_update(index_elements=["content_id"], set_=columns)
    await session.execute(stmt)
    await session.commit()


async def fetch_detail_common(
    kto: KtoClient, content_id: str
) -> tuple[str | None, str | None, str | None]:
    items = await kto.call(KtoService.KOR, "detailCommon2", contentId=content_id)
    common = items[0] if items else {}
    return (
        verbatim(common.get("overview")),
        clean_homepage(common.get("homepage")),
        clean_scalar(common.get("tel")),
    )


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
                Spot.cpyrht_div_cd,
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


def parse_kto_detail_images(items: list[dict[str, Any]]) -> list[SpotImageRow]:
    images: list[SpotImageRow] = []
    for item in items:
        origin = clean_scalar(item.get("originimgurl"))
        if origin is None:
            continue
        images.append(
            SpotImageRow(
                origin_image_url=origin,
                small_image_url=clean_scalar(item.get("smallimageurl")),
                cpyrht_div_cd=clean_scalar(item.get("cpyrhtDivCd")),
            )
        )
    return images


_KTO_DETAIL_BUDGET = 8.0


@dataclass(frozen=True)
class _KtoDetail:
    """오퍼레이션별 성공 여부를 들고 다닌다 — 실패한 칸을 DB 에 NULL 로 덮어쓰지 않으려고."""

    overview: str | None
    homepage: str | None
    tel: str | None
    images: list[SpotImageRow]
    intro_data: dict[str, Any] | None
    common_ok: bool
    images_ok: bool
    intro_ok: bool

    @property
    def complete(self) -> bool:
        return self.common_ok and self.images_ok and self.intro_ok


def _settled(outcome: Any) -> list[dict[str, Any]] | None:
    return None if isinstance(outcome, BaseException) else cast("list[dict[str, Any]]", outcome)


async def _fetch_kto_detail(kto: KtoClient, content_id: str, content_type_id: int) -> _KtoDetail:
    """세 오퍼레이션을 독립으로 정산한다 — detailCommon2 쿼터 초과가 나머지 둘을 버리지 않게."""
    try:
        outcomes = await asyncio.wait_for(
            asyncio.gather(
                kto.call(KtoService.KOR, "detailCommon2", contentId=content_id),
                kto.call(KtoService.KOR, "detailImage2", contentId=content_id, imageYN="Y"),
                kto.call(
                    KtoService.KOR,
                    "detailIntro2",
                    contentId=content_id,
                    contentTypeId=content_type_id,
                ),
                return_exceptions=True,
            ),
            timeout=_KTO_DETAIL_BUDGET,
        )
    except TimeoutError as exc:
        raise KtoApiUnavailable("KTO detail fetch exceeded budget") from exc

    common_items = _settled(outcomes[0])
    image_items = _settled(outcomes[1])
    intro_items = _settled(outcomes[2])
    if common_items is None and image_items is None and intro_items is None:
        logger.warning("spot.detail.kto_all_failed", content_id=content_id)
        raise KtoApiUnavailable("every KTO detail operation failed")
    if common_items is None or image_items is None or intro_items is None:
        logger.info(
            "spot.detail.kto_partial",
            content_id=content_id,
            common=common_items is not None,
            images=image_items is not None,
            intro=intro_items is not None,
        )

    common = common_items[0] if common_items else {}
    return _KtoDetail(
        overview=verbatim(common.get("overview")),
        homepage=clean_homepage(common.get("homepage")),
        tel=clean_scalar(common.get("tel")),
        images=parse_kto_detail_images(image_items or []),
        intro_data=(intro_items[0] if intro_items else {}) if intro_items is not None else None,
        common_ok=common_items is not None,
        images_ok=image_items is not None,
        intro_ok=intro_items is not None,
    )


def _serves(cache: _DetailCache | None, *, require_intro: bool) -> bool:
    if cache is None:
        return False
    return not require_intro or cache.intro_data is not None


async def load_spot_detail(
    session: AsyncSession,
    kto: KtoClient,
    redis: Redis,
    content_id: str,
    *,
    defer_refresh: bool = False,
    require_intro: bool = False,
) -> SpotDetailRow:
    spot = await _load_spot_context(session, content_id)
    ctx = _DetailContext(spot, spot.region_name, spot.sigungu_name, spot.category)

    cache = await _redis_get_detail(redis, content_id)
    redis_fresh = cache is not None and _is_fresh(cache.cached_at, spot.modified_time)
    if not redis_fresh or not _serves(cache, require_intro=require_intro):
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

    if (
        cache is not None
        and _is_fresh(cache.cached_at, spot.modified_time)
        and _serves(cache, require_intro=require_intro)
    ):
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

    if defer_refresh:
        if cache is not None:
            return ctx.assemble(
                overview=cache.overview,
                homepage=cache.homepage,
                tel=cache.tel,
                images=cache.images,
                status="stale",
                intro=_extract_intro(spot.content_type_id, cache.intro_data),
            )
        status = "unavailable" if await _refresh_in_backoff(redis, content_id) else "pending"
        return ctx.assemble(
            overview=None,
            homepage=None,
            tel=None,
            images=[],
            status=status,
            intro=None,
        )

    try:
        fetched = await _fetch_kto_detail(kto, content_id, spot.content_type_id)
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

    merged = _merge_with_cache(fetched, cache)
    await _persist_detail(session, content_id, spot.content_type_id, fetched)
    if fetched.complete:
        await _redis_set_detail(
            redis,
            content_id,
            _DetailCache(
                overview=merged.overview,
                homepage=merged.homepage,
                tel=merged.tel,
                intro_data=merged.intro_data,
                cached_at=datetime.now(UTC),
                images=merged.images,
            ),
        )

    return ctx.assemble(
        overview=merged.overview,
        homepage=merged.homepage,
        tel=merged.tel,
        images=merged.images,
        status="fresh" if fetched.complete else "stale",
        intro=_extract_intro(spot.content_type_id, merged.intro_data),
    )


async def refresh_spot_detail(
    session: AsyncSession,
    kto: KtoClient,
    redis: Redis,
    content_id: str,
) -> None:
    if await _refresh_in_backoff(redis, content_id):
        return
    acquired, lock_token = await _acquire_refresh_lock(redis, content_id)
    if not acquired:
        return
    try:
        row = await load_spot_detail(session, kto, redis, content_id)
        if row.detail_status in {"stale", "unavailable"}:
            await _set_refresh_backoff(redis, content_id)
    except Exception as exc:
        await _set_refresh_backoff(redis, content_id)
        logger.warning("spot.detail.refresh_failed", content_id=content_id, error=str(exc))
    finally:
        await _release_refresh_lock(redis, content_id, lock_token)


async def refresh_spot_detail_in_background(
    kto: KtoClient,
    redis: Redis,
    content_id: str,
) -> None:
    async with async_session_factory() as session:
        await refresh_spot_detail(session, kto, redis, content_id)
