"""Related spots — KTO TarRlteTar "places people search together"
(ADR-0005 live + Redis, ADR-0015)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import KtoApiUnavailable, ResourceNotFound
from app.core.kto_client import KtoClient, KtoService
from app.core.logging import get_logger
from app.core.text import clean_scalar
from app.modules.spots.models import Spot
from app.modules.spots.services.rows import RelatedSpotRow

logger = get_logger(__name__)


_RLTE_KEY = "rlte:{content_id}"
_RLTE_TTL = 3600  # 1h, ADR-0005
_RLTE_LIMIT = 15
_TARRLTE_PAGE = 1000
_TARRLTE_MAX_PAGES = 3  # covers the largest sigungu/district (~1.5k rows) in one fetch
_BASEYM_LOOKBACK = 6  # TarRlteTar publishes monthly with a 1-2 month lag


def _norm_name(value: str | None) -> str:
    """Loose key for matching a spot title to a TarRlteTar `tAtsNm`. Drops the
    trailing variant after '/' (e.g. "김유정역/폐역" → "김유정역") and all
    whitespace."""
    if not value:
        return ""
    return re.sub(r"\s+", "", value.split("/", 1)[0]).lower()


def _to_int(value: Any) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _recent_year_months(n: int) -> list[str]:
    now = datetime.now(UTC)
    year, month = now.year, now.month
    out: list[str] = []
    for _ in range(n):
        out.append(f"{year}{month:02d}")
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return out


async def list_related_spots(
    session: AsyncSession,
    kto: KtoClient,
    redis: Redis,
    content_id: str,
) -> list[RelatedSpotRow]:
    """ "Places people search together" for a spot, from KTO TarRlteTar
    (ADR-0005/0015).

    Read path: Redis `rlte:{contentId}` (1h) → on miss, fetch TarRlteTar for the
    spot's sido/sigungu (province/district), keep the rows whose base name
    matches this spot, resolve
    names back to our active spots for optional deep-linking, and cache. KTO is
    supplementary here: an upstream failure yields an empty list, never a 502.
    Raises ResourceNotFound if the spot is absent or hidden.
    """
    spot = (
        await session.execute(
            select(Spot.title, Spot.ldong_regn_cd, Spot.ldong_signgu_cd).where(
                Spot.content_id == content_id, Spot.show_flag == 1
            )
        )
    ).first()
    if spot is None:
        raise ResourceNotFound(f"Spot '{content_id}' not found.")

    cached = await _rlte_cache_get(redis, content_id)
    if cached is not None:
        return cached

    rows: list[RelatedSpotRow] = []
    if spot.ldong_regn_cd and spot.ldong_signgu_cd:
        rows = await _fetch_related_from_kto(
            session, kto, spot.title, spot.ldong_regn_cd, spot.ldong_signgu_cd
        )
    await _rlte_cache_set(redis, content_id, rows)
    return rows


async def _fetch_related_from_kto(
    session: AsyncSession,
    kto: KtoClient,
    title: str,
    regn_cd: str,
    signgu_cd: str,
) -> list[RelatedSpotRow]:
    target = _norm_name(title)
    for base_ym in _recent_year_months(_BASEYM_LOOKBACK):
        items: list[dict[str, Any]] = []
        for page in range(1, _TARRLTE_MAX_PAGES + 1):
            try:
                batch = await kto.call(
                    KtoService.TARRLTE,
                    "areaBasedList1",
                    baseYm=base_ym,
                    areaCd=regn_cd,
                    signguCd=signgu_cd,
                    numOfRows=_TARRLTE_PAGE,
                    pageNo=page,
                )
            except KtoApiUnavailable:
                return []  # supplementary — degrade to empty, never raise
            if not batch:
                break
            items.extend(batch)
            if len(batch) < _TARRLTE_PAGE:
                break
        if not items:
            continue  # month has no data — walk back to an older baseYm
        related = [it for it in items if _norm_name(it.get("tAtsNm")) == target]
        return await _build_related(session, related)
    return []


async def _build_related(
    session: AsyncSession, items: list[dict[str, Any]]
) -> list[RelatedSpotRow]:
    by_name: dict[str, dict[str, Any]] = {}
    for it in items:
        name = clean_scalar(it.get("rlteTatsNm"))
        if name and name not in by_name:
            by_name[name] = it
    ordered = sorted(by_name.values(), key=lambda it: _to_int(it.get("rlteRank")))[:_RLTE_LIMIT]
    names = [clean_scalar(it.get("rlteTatsNm")) for it in ordered]
    names = [n for n in names if n]

    id_by_name: dict[str, str] = {}
    if names:
        recs = await session.execute(
            select(Spot.title, Spot.content_id).where(Spot.title.in_(names), Spot.show_flag == 1)
        )
        for row_title, cid in recs:
            id_by_name.setdefault(row_title, cid)

    out: list[RelatedSpotRow] = []
    for it in ordered:
        name = clean_scalar(it.get("rlteTatsNm"))
        if not name:
            continue
        region = " ".join(
            x
            for x in (clean_scalar(it.get("rlteRegnNm")), clean_scalar(it.get("rlteSignguNm")))
            if x
        )
        out.append(
            RelatedSpotRow(
                name=name,
                category=clean_scalar(it.get("rlteCtgryMclsNm"))
                or clean_scalar(it.get("rlteCtgryLclsNm")),
                region_name=region or None,
                address=clean_scalar(it.get("rlteBsicAdres")),
                rank=_to_int(it.get("rlteRank")) or None,
                content_id=id_by_name.get(name),
            )
        )
    return out


async def _rlte_cache_get(redis: Redis, content_id: str) -> list[RelatedSpotRow] | None:
    """Return the cached rows, [] for a cached empty result, or None on miss /
    Redis error (treat a dead cache as a miss, not a failure — ADR-0005)."""
    try:
        raw = await redis.get(_RLTE_KEY.format(content_id=content_id))
    except Exception as exc:  # cache is non-critical
        logger.warning("spt.related.cache_get_failed", content_id=content_id, error=str(exc))
        return None
    if raw is None:
        return None
    try:
        return [RelatedSpotRow(**d) for d in json.loads(raw)]
    except (ValueError, TypeError):
        logger.warning("spt.related.cache_bad_payload", content_id=content_id)
        return None


async def _rlte_cache_set(redis: Redis, content_id: str, rows: list[RelatedSpotRow]) -> None:
    try:
        payload = json.dumps([asdict(r) for r in rows], ensure_ascii=False)
        await redis.set(_RLTE_KEY.format(content_id=content_id), payload, ex=_RLTE_TTL)
    except Exception as exc:  # cache write best-effort
        logger.warning("spt.related.cache_set_failed", content_id=content_id, error=str(exc))
