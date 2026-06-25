"""MAP service layer — nearby enrichment + region reverse geocode."""

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from app.core.db import AsyncSession
from app.core.kakao_local import kakao_local_get
from app.core.logging import get_logger
from app.modules.map import repositories as repo
from app.modules.map.schemas import RegionLabel
from app.modules.spots.services import (
    NearbyCategory,
    NearbySpotRow,
    find_nearby_spots,
    load_congestion,
    load_region_meta,
)

logger = get_logger(__name__)

_NEARBY_LIMIT = 30
_REGION_CACHE_KEY = "region:{lat:.3f}:{lng:.3f}"
_REGION_CACHE_TTL = 86_400  # 1 day
_COORD2REGIONCODE_PATH = "/geo/coord2regioncode.json"

REGIONS_TREE_KEY = "regions:tree"
_REGIONS_TREE_TTL = 86_400  # 24h — the tree is administrative + slow-moving.


async def nearby_spots(
    session: AsyncSession,
    *,
    lat: float,
    lng: float,
    radius: int,
    category: NearbyCategory | None,
) -> list[NearbySpotRow]:
    """Merge congestion + region meta onto SPT's distance-ranked rows, capped at 30."""
    rows = await find_nearby_spots(session, lat=lat, lng=lng, radius=radius, category=category)
    rows = rows[:_NEARBY_LIMIT]
    if not rows:
        return rows

    content_ids = [r.content_id for r in rows]
    congestion_by_id = await load_congestion(session, content_ids)
    region_by_id = await load_region_meta(session, content_ids)
    for row in rows:
        row.congestion = congestion_by_id.get(row.content_id)
        region_name, sigungu_name = region_by_id.get(row.content_id, (None, None))
        row.region_name = region_name
        row.sigungu_name = sigungu_name
    return rows


def _to_region_label(payload: dict[str, Any]) -> RegionLabel | None:
    docs = payload.get("documents") or []
    if not docs:
        return None
    # Prefer administrative-dong (H), else first document.
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

    Failures and empty responses degrade to None for a generic "near me" fallback.
    """
    key = _REGION_CACHE_KEY.format(lat=lat, lng=lng)
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
        except ValueError as exc:  # UnicodeDecodeError + pydantic ValidationError
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


async def regions_tree(session: AsyncSession, redis: Redis) -> list[dict[str, Any]]:
    """17 sido + their sigungus, each with a runtime-AVG centroid, cached 24h."""
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

    regions = await repo.fetch_regions(session)
    sigungus = await repo.fetch_sigungus(session)
    sido_centroids = await repo.fetch_sido_centroids(session)
    sigungu_centroids = await repo.fetch_sigungu_centroids(session)

    sigungus_by_regn: dict[str, list[Any]] = {}
    for sg in sigungus:
        sigungus_by_regn.setdefault(sg.ldong_regn_cd, []).append(sg)

    tree: list[dict[str, Any]] = []
    for region in regions:
        sido_lng, sido_lat = sido_centroids.get(region.ldong_regn_cd, (0.0, 0.0))
        sg_nodes: list[dict[str, Any]] = []
        for sg in sigungus_by_regn.get(region.ldong_regn_cd, []):
            # A sigungu with no visible spots falls back to its sido centroid.
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
