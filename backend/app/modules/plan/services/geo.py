from __future__ import annotations

import math

from app.modules.plan.schemas import ResolvedSpot

NEAR_DUPLICATE_KM = 0.4

_EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def spot_distance_km(a: ResolvedSpot | None, b: ResolvedSpot | None) -> float | None:
    if a is None or b is None:
        return None
    if a.lat is None or a.lng is None or b.lat is None or b.lng is None:
        return None
    return haversine_km(a.lat, a.lng, b.lat, b.lng)


def is_near_duplicate(spot: ResolvedSpot | None, others: list[ResolvedSpot]) -> bool:
    for other in others:
        distance = spot_distance_km(spot, other)
        if distance is not None and distance <= NEAR_DUPLICATE_KM:
            return True
    return False
