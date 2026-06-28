"""Spots upsert / soft-delete logic."""

from __future__ import annotations

import psycopg

from pictrip_data.kto.schemas import KtoSpot
from pictrip_data.sync.refcodes import RefCodes

_COLS = (
    "content_id",
    "content_type_id",
    "title",
    "addr1",
    "addr2",
    "zipcode",
    "mapx",
    "mapy",
    "ldong_regn_cd",
    "ldong_signgu_cd",
    "lcls_systm1",
    "lcls_systm2",
    "lcls_systm3",
    "cpyrht_div_cd",
    "first_image_url",
    "first_image2_url",
    "show_flag",
    "modified_time",
)

_UPDATE = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLS if c != "content_id")

_SQL = f"""
INSERT INTO spots ({", ".join(_COLS)})
VALUES ({", ".join("%s" for _ in _COLS)})
ON CONFLICT (content_id) DO UPDATE SET {_UPDATE}, synced_at = now()
WHERE spots.modified_time IS NULL OR spots.modified_time < EXCLUDED.modified_time
RETURNING (xmax = 0) AS inserted, show_flag
"""


def _row(spot: KtoSpot, refs: RefCodes) -> tuple:
    regn = spot.ldong_regn_cd if spot.ldong_regn_cd in refs.regn else None
    signgu = spot.ldong_signgu_cd if spot.ldong_signgu_cd in refs.signgu else None
    lcls3 = spot.lcls_systm3 if spot.lcls_systm3 in refs.lcls3 else None
    return (
        spot.content_id,
        spot.content_type_id,
        spot.title,
        spot.addr1,
        spot.addr2,
        spot.zipcode,
        spot.mapx,
        spot.mapy,
        regn,
        signgu,
        spot.lcls_systm1,
        spot.lcls_systm2,
        lcls3,
        spot.cpyrht_div_cd,
        spot.first_image_url,
        spot.first_image2_url,
        spot.show_flag,
        spot.modified_time,
    )


def upsert_spots(
    conn: psycopg.Connection, spots: list[KtoSpot], refs: RefCodes, counters: dict[str, int]
) -> None:
    cur = conn.cursor()
    for spot in spots:
        cur.execute(_SQL, _row(spot, refs))
        result = cur.fetchone()
        if result is None:
            counters["skipped"] += 1  # newer-wins guard blocked a stale row
            continue
        inserted, show_flag = result
        if show_flag == 0:
            counters["soft_deleted"] += 1
        elif inserted:
            counters["inserted"] += 1
        else:
            counters["updated"] += 1
