from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from app.core.db import AsyncSession
from app.core.exceptions import ValidationFailed
from app.core.logging import get_logger
from app.modules.map import repositories as repo
from app.modules.map.kakao_local import kakao_local_get
from app.modules.map.schemas import NearbySpotCard, RegionLabel
from app.modules.spots.services import (
    NearbyCategory,
    NearbySpotRow,
    find_nearby_spots,
    find_nearby_spots_bbox,
    load_region_meta,
)

logger = get_logger(__name__)

_NEARBY_LIMIT = 30
_REGION_CACHE_KEY = "region:{lat:.3f}:{lng:.3f}"
_REGION_CACHE_TTL = 86_400
_COORD2REGIONCODE_PATH = "/geo/coord2regioncode.json"

REGIONS_TREE_KEY = "regions:tree"
_REGIONS_TREE_TTL = 86_400


async def _enrich(session: AsyncSession, rows: list[NearbySpotRow]) -> list[NearbySpotRow]:
    rows = rows[:_NEARBY_LIMIT]
    if not rows:
        return rows

    content_ids = [r.content_id for r in rows]
    region_by_id = await load_region_meta(session, content_ids)
    for row in rows:
        region_name, sigungu_name = region_by_id.get(row.content_id, (None, None))
        row.region_name = region_name
        row.sigungu_name = sigungu_name
    return rows


async def nearby_spots(
    session: AsyncSession,
    *,
    lat: float,
    lng: float,
    radius: int,
    category: NearbyCategory | None,
) -> list[NearbySpotRow]:
    rows = await find_nearby_spots(session, lat=lat, lng=lng, radius=radius, category=category)
    return await _enrich(session, rows)


async def nearby_spots_bbox(
    session: AsyncSession,
    *,
    sw_lat: float,
    sw_lng: float,
    ne_lat: float,
    ne_lng: float,
    category: NearbyCategory | None,
) -> list[NearbySpotRow]:
    rows = await find_nearby_spots_bbox(
        session,
        sw_lat=sw_lat,
        sw_lng=sw_lng,
        ne_lat=ne_lat,
        ne_lng=ne_lng,
        category=category,
    )
    return await _enrich(session, rows)


async def nearby_cards(
    session: AsyncSession,
    *,
    lat: float | None,
    lng: float | None,
    radius: int,
    category: NearbyCategory | None,
    sw_lat: float | None,
    sw_lng: float | None,
    ne_lat: float | None,
    ne_lng: float | None,
) -> list[NearbySpotCard]:
    if sw_lat is not None and sw_lng is not None and ne_lat is not None and ne_lng is not None:
        rows = await nearby_spots_bbox(
            session, sw_lat=sw_lat, sw_lng=sw_lng, ne_lat=ne_lat, ne_lng=ne_lng, category=category
        )
    elif lat is not None and lng is not None:
        rows = await nearby_spots(session, lat=lat, lng=lng, radius=radius, category=category)
    else:
        raise ValidationFailed("Provide either a bbox (sw_lat/sw_lng/ne_lat/ne_lng) or lat+lng.")
    return [
        NearbySpotCard(
            contentId=r.content_id,
            title=r.title,
            firstImageUrl=r.first_image_url,
            addr1=r.addr1,
            mapx=r.mapx,
            mapy=r.mapy,
            dist=r.dist,
            category=r.category,
            categoryGroup=r.category_group,
            regionName=r.region_name,
            sigunguName=r.sigungu_name,
            overview=r.overview,
        )
        for r in rows
    ]


def _to_region_label(payload: dict[str, Any]) -> RegionLabel | None:
    docs = payload.get("documents") or []
    if not docs:
        return None
    doc = next((d for d in docs if d.get("region_type") == "H"), docs[0])
    sido = doc.get("region_1depth_name") or None
    sigungu = doc.get("region_2depth_name") or None
    dong = doc.get("region_3depth_name") or None
    label = " ".join(p for p in (sigungu, dong) if p).strip()
    if not label:
        return None
    return RegionLabel(sido=sido, sigungu=sigungu, dong=dong, label=label)


async def reverse_geocode(redis: Redis, *, lat: float, lng: float) -> RegionLabel | None:
    key = _REGION_CACHE_KEY.format(lat=lat, lng=lng)
    cached = None
    try:
        cached = await redis.get(key)
    except Exception as exc:
        logger.warning("map.region.cache_get_failed", error=str(exc))
    if cached is not None:
        try:
            raw = cached.decode() if isinstance(cached, bytes) else cached
            if raw == "null":
                return None
            return RegionLabel.model_validate_json(raw)
        except ValueError as exc:
            logger.warning("map.region.cache_corrupt", error=str(exc))

    payload = await kakao_local_get(_COORD2REGIONCODE_PATH, params={"x": lng, "y": lat})
    if payload is None:
        return None
    label = _to_region_label(payload)

    try:
        await redis.set(key, label.model_dump_json() if label else "null", ex=_REGION_CACHE_TTL)
    except Exception as exc:
        logger.warning("map.region.cache_set_failed", error=str(exc))
    return label


async def regions_tree(session: AsyncSession, redis: Redis) -> list[dict[str, Any]]:
    try:
        cached = await redis.get(REGIONS_TREE_KEY)
    except Exception as exc:
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
    except Exception as exc:
        logger.warning("map.regions_tree.cache_set_failed", error=str(exc))
    return tree
