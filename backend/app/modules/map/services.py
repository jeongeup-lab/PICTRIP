"""MAP service layer — crowd(Redis) 머지 + region reverse geocode.

nearby 쿼리(bbox+haversine+카테고리)와 taxonomy는 SPT가 소유한다
(`app.modules.spots.services.find_nearby_spots`). MAP은 그 행에 crowd 지표를 머지한다:
Redis(`crowd:{contentId}`; crowd는 Redis-only, `crowd_metrics` 테이블 없음)에서 조회해
카드에 붙이고, 없으면 `crowd = None`(graceful fallback, 에러 아님).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.kakao_local import kakao_local_get
from app.core.logging import get_logger
from app.modules.map.schemas import RegionLabel
from app.modules.spots.services import NearbyCategory, find_nearby_spots

logger = get_logger(__name__)

_CROWD_KEY = "crowd:{content_id}"
_REGION_CACHE_KEY = "region:{lat:.3f}:{lng:.3f}"
_REGION_CACHE_TTL = 86_400  # 1 day
_COORD2REGIONCODE_PATH = "/geo/coord2regioncode.json"

REGIONS_TREE_KEY = "regions:tree"
_REGIONS_TREE_TTL = 86_400  # 24h — the tree is administrative + slow-moving.


@dataclass
class CrowdRow:
    """Crowd metric for a single spot (rate 0..1, level easy|normal|crowded)."""

    rate: float
    level: str


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
    category: str | None = None  # SPT가 파생한 칩 코드
    overview: str | None = None  # KTO overview(verbatim), 대부분 None — 카드 설명 줄
    crowd: CrowdRow | None = None


def merge_crowd(
    spots: list[NearbySpotRow],
    crowd_by_id: dict[str, CrowdRow],
) -> list[NearbySpotRow]:
    """Attach crowd metrics where a matching row exists; leave `crowd=None` else.

    Pure function (no I/O) so it is unit-testable in isolation. The fallback when
    a spot has no crowd entry is an explicit `None` — callers/clients branch on
    presence, never on an error.
    """
    for spot in spots:
        spot.crowd = crowd_by_id.get(spot.content_id)
    return spots


async def _load_crowd(redis: Redis, content_ids: list[str]) -> dict[str, CrowdRow]:
    """Best-effort crowd lookup from Redis. Missing/corrupt rows are skipped.

    Redis being unavailable must NOT fail the whole request — nearby spots are
    still useful without crowd info — so errors degrade to an empty mapping.
    """
    if not content_ids:
        return {}
    try:
        keys = [_CROWD_KEY.format(content_id=cid) for cid in content_ids]
        raw_values = await redis.mget(keys)
    except Exception as exc:  # crowd is non-critical; degrade gracefully
        logger.warning("map.crowd.lookup_failed", error=str(exc))
        return {}

    out: dict[str, CrowdRow] = {}
    for content_id, raw in zip(content_ids, raw_values, strict=True):
        if not raw:
            continue
        try:
            payload = json.loads(raw)
            out[content_id] = CrowdRow(rate=float(payload["rate"]), level=str(payload["level"]))
        except (ValueError, KeyError, TypeError):
            logger.warning("map.crowd.bad_payload", content_id=content_id)
            continue
    return out


async def nearby_spots(
    session: AsyncSession,
    redis: Redis,
    *,
    lat: float,
    lng: float,
    radius: int,
    category: NearbyCategory | None,
) -> list[NearbySpotRow]:
    """SPT의 거리순 nearby 행에 crowd(Redis)를 graceful 머지한다."""
    spt_rows = await find_nearby_spots(session, lat=lat, lng=lng, radius=radius, category=category)
    rows = [
        NearbySpotRow(
            content_id=s.content_id,
            title=s.title,
            first_image_url=s.first_image_url,
            first_image2_url=s.first_image2_url,
            addr1=s.addr1,
            mapx=s.mapx,
            mapy=s.mapy,
            dist=s.dist,
            category=s.category,
            overview=s.overview,
        )
        for s in spt_rows
    ]
    crowd_by_id = await _load_crowd(redis, [r.content_id for r in rows])
    return merge_crowd(rows, crowd_by_id)


def _to_region_label(payload: dict[str, Any]) -> RegionLabel | None:
    docs = payload.get("documents") or []
    if not docs:
        return None
    # Prefer administrative-dong (H), then fall back to the first document.
    doc = next((d for d in docs if d.get("region_type") == "H"), docs[0])
    sido = doc.get("region_1depth_name") or None
    sigungu = doc.get("region_2depth_name") or None
    dong = doc.get("region_3depth_name") or None
    label = " ".join(p for p in (sigungu, dong) if p).strip()
    if not label:
        return None
    return RegionLabel(sido=sido, sigungu=sigungu, dong=dong, label=label)


async def reverse_geocode(redis: Redis, *, lat: float, lng: float) -> RegionLabel | None:
    """Return a region label from Kakao coord2regioncode with Redis caching.

    Failures and empty responses degrade to None so the client can display its
    generic "near me" fallback.
    """
    key = _REGION_CACHE_KEY.format(lat=lat, lng=lng)
    # Dead cache = miss. Redis outages or corrupt cache must not turn region
    # lookup into a 500.
    cached = None
    try:
        cached = await redis.get(key)
    except Exception as exc:  # cache is non-critical
        logger.warning("map.region.cache_get_failed", error=str(exc))
    if cached is not None:
        try:
            raw = cached.decode() if isinstance(cached, bytes) else cached
            if raw == "null":
                return None
            return RegionLabel.model_validate_json(raw)
        except ValueError as exc:  # includes UnicodeDecodeError and pydantic ValidationError
            logger.warning("map.region.cache_corrupt", error=str(exc))

    payload = await kakao_local_get(_COORD2REGIONCODE_PATH, params={"x": lng, "y": lat})
    if payload is None:
        return None
    label = _to_region_label(payload)

    try:
        await redis.set(key, label.model_dump_json() if label else "null", ex=_REGION_CACHE_TTL)
    except Exception as exc:  # cache write best-effort
        logger.warning("map.region.cache_set_failed", error=str(exc))
    return label


# Centroids are runtime AVG of visible spot coordinates. mapx=lng, mapy=lat
# (S07 ERD) — do not swap. The "{시도} 전체" centroid is the sido-scope AVG; a
# sigungu with no spots COALESCEs to that sido centroid.
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


async def regions_tree(session: AsyncSession, redis: Redis) -> list[dict[str, Any]]:
    """17 sido + their sigungus, each with a runtime-AVG centroid, cached 24h.

    Centroids are computed once over the whole spots table (two GROUP BY scans)
    rather than per-row to keep the assembly O(regions + sigungus). A sigungu
    with no visible spots falls back to its sido centroid; the cache stores the
    fully assembled JSON so subsequent reads skip the DB entirely.
    """
    try:
        cached = await redis.get(REGIONS_TREE_KEY)
    except Exception as exc:  # cache is non-critical — degrade to a rebuild.
        logger.warning("map.regions_tree.cache_get_failed", error=str(exc))
        cached = None
    if cached is not None:
        try:
            raw = cached.decode() if isinstance(cached, bytes) else cached
            return list(json.loads(raw))
        except (ValueError, TypeError) as exc:
            logger.warning("map.regions_tree.cache_corrupt", error=str(exc))

    regions = (
        await session.execute(
            text("SELECT ldong_regn_cd, ldong_regn_nm FROM regions ORDER BY ldong_regn_cd")
        )
    ).all()
    sigungus = (
        await session.execute(
            text(
                "SELECT ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm FROM sigungus "
                "ORDER BY ldong_signgu_cd"
            )
        )
    ).all()
    sido_centroids = {
        r.code: (float(r.cx), float(r.cy))
        for r in (await session.execute(_SIDO_CENTROID_SQL)).all()
        if r.cx is not None and r.cy is not None
    }
    sigungu_centroids = {
        r.code: (float(r.cx), float(r.cy))
        for r in (await session.execute(_SIGUNGU_CENTROID_SQL)).all()
        if r.cx is not None and r.cy is not None
    }

    sigungus_by_regn: dict[str, list[Any]] = {}
    for sg in sigungus:
        sigungus_by_regn.setdefault(sg.ldong_regn_cd, []).append(sg)

    tree: list[dict[str, Any]] = []
    for region in regions:
        sido_lng, sido_lat = sido_centroids.get(region.ldong_regn_cd, (0.0, 0.0))
        sg_nodes: list[dict[str, Any]] = []
        for sg in sigungus_by_regn.get(region.ldong_regn_cd, []):
            lng, lat = sigungu_centroids.get(sg.ldong_signgu_cd, (sido_lng, sido_lat))
            sg_nodes.append(
                {
                    "sigunguCode": sg.ldong_signgu_cd,
                    "sigunguName": sg.ldong_signgu_nm,
                    "centroid": {"lat": lat, "lng": lng},
                }
            )
        tree.append(
            {
                "regionCode": region.ldong_regn_cd,
                "regionName": region.ldong_regn_nm,
                "centroid": {"lat": sido_lat, "lng": sido_lng},
                "sigungus": sg_nodes,
            }
        )

    try:
        await redis.set(REGIONS_TREE_KEY, json.dumps(tree), ex=_REGIONS_TREE_TTL)
    except Exception as exc:  # cache write best-effort
        logger.warning("map.regions_tree.cache_set_failed", error=str(exc))
    return tree
