"""One-shot loader for region / classification master codes.

Idempotent upsert from two KorService2 endpoints:
  - ldongCode2 (lDongListYn=Y)   -> regions + sigungus (composite signgu code)
  - lclsSystmCode2 (lclsSystmListYn=Y) -> lcls_systm_codes

Run manually, not on cron. Owns the same ref tables that upsert.py FK-checks.
"""

from __future__ import annotations

from typing import Any

import psycopg

from pictrip_data.db import connect
from pictrip_data.kto.client import KtoClient
from pictrip_data.kto.schemas import normalize_regn_cd

_REGION_SQL = """
INSERT INTO regions (ldong_regn_cd, ldong_regn_nm)
VALUES (%s, %s)
ON CONFLICT (ldong_regn_cd) DO UPDATE SET ldong_regn_nm = EXCLUDED.ldong_regn_nm
"""

_SIGUNGU_SQL = """
INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm)
VALUES (%s, %s, %s)
ON CONFLICT (ldong_signgu_cd) DO UPDATE SET
    ldong_regn_cd = EXCLUDED.ldong_regn_cd,
    ldong_signgu_nm = EXCLUDED.ldong_signgu_nm
"""

_LCLS_SQL = """
INSERT INTO lcls_systm_codes (
    lcls_systm3_cd, lcls_systm3_nm, lcls_systm2_cd, lcls_systm1_cd,
    lcls_systm2_nm, lcls_systm1_nm
)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (lcls_systm3_cd) DO UPDATE SET
    lcls_systm3_nm = EXCLUDED.lcls_systm3_nm,
    lcls_systm2_cd = EXCLUDED.lcls_systm2_cd,
    lcls_systm1_cd = EXCLUDED.lcls_systm1_cd,
    lcls_systm2_nm = EXCLUDED.lcls_systm2_nm,
    lcls_systm1_nm = EXCLUDED.lcls_systm1_nm
"""


def _load_ldong(client: KtoClient, conn: psycopg.Connection) -> None:
    rows = client.call("ldongCode2", lDongListYn="Y", numOfRows=400)
    # Dedup regions in Python: the ldong list repeats the region per sigungu.
    regions: dict[str, str] = {}
    sigungus: list[tuple[str, str, str]] = []
    for r in rows:
        # Sejong's province code is the 5-char '36110'; normalize to 2-char so it
        # fits regions/sigungus (varchar 8) and matches existing data.
        regn_cd = normalize_regn_cd(str(r["lDongRegnCd"]))
        regn_nm = str(r["lDongRegnNm"])
        signgu_cd = str(r["lDongSignguCd"])
        signgu_nm = str(r["lDongSignguNm"])
        regions[regn_cd] = regn_nm
        sigungus.append((f"{regn_cd}{signgu_cd}", regn_cd, signgu_nm))

    cur = conn.cursor()
    # regions first (sigungus FK them).
    cur.executemany(_REGION_SQL, list(regions.items()))
    cur.executemany(_SIGUNGU_SQL, sigungus)


def _load_lcls(client: KtoClient, conn: psycopg.Connection) -> None:
    rows = client.call("lclsSystmCode2", lclsSystmListYn="Y", numOfRows=300)
    values = [
        (
            str(r["lclsSystm3Cd"]),
            str(r["lclsSystm3Nm"]),
            str(r["lclsSystm2Cd"]),
            str(r["lclsSystm1Cd"]),
            str(r["lclsSystm2Nm"]),
            str(r["lclsSystm1Nm"]),
        )
        for r in rows
    ]
    conn.cursor().executemany(_LCLS_SQL, values)


def _run(client: KtoClient, conn: psycopg.Connection) -> None:
    _load_ldong(client, conn)
    _load_lcls(client, conn)  # independent of regions/sigungus
    conn.commit()


def load_codes(client: Any | None = None, conn: psycopg.Connection | None = None) -> None:
    """Load region / sigungu / lcls master codes idempotently. Builds its own
    KtoClient + DB connection when not injected (same ownership pattern as
    sync_daily)."""
    owns_client = client is None
    client = client or KtoClient()
    try:
        if conn is None:
            with connect() as conn:
                _run(client, conn)
        else:
            _run(client, conn)
    finally:
        if owns_client:
            client.close()
