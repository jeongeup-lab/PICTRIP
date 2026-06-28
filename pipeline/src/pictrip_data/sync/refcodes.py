from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass
class RefCodes:
    regn: set[str]
    signgu: set[str]
    lcls3: set[str]


def load_ref_codes(conn: psycopg.Connection) -> RefCodes:
    cur = conn.cursor()
    cur.execute("SELECT ldong_regn_cd FROM regions")
    regn = {r[0] for r in cur.fetchall()}
    cur.execute("SELECT ldong_signgu_cd FROM sigungus")
    signgu = {r[0] for r in cur.fetchall()}
    cur.execute("SELECT lcls_systm3_cd FROM lcls_systm_codes")
    lcls3 = {r[0] for r in cur.fetchall()}
    return RefCodes(regn=regn, signgu=signgu, lcls3=lcls3)
