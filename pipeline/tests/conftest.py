import os

import psycopg
import pytest

TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://pictrip:pictrip_dev_only@localhost:5432/pictrip_test",
)

# Every test content_id starts with this prefix so cleanup is targeted.
TEST_PREFIX = "T"
# Real fixture ids used by sync_daily test (not prefixed) — clean these too.
FIXTURE_IDS = ("2865520", "3509884")


# Minimal schema the DB-integration tests need. CREATE ... IF NOT EXISTS makes
# this a no-op against the locally-migrated pictrip_test (backend Alembic head),
# and self-bootstraps a fresh empty Postgres in CI (no backend dependency).
# Column types/FKs mirror the live spots schema; sync_runs is created separately
# by the pipeline's own ensure_table().
_SCHEMA = """
CREATE TABLE IF NOT EXISTS regions (
    ldong_regn_cd varchar(8) PRIMARY KEY,
    ldong_regn_nm varchar(64) NOT NULL
);
CREATE TABLE IF NOT EXISTS sigungus (
    ldong_signgu_cd varchar(8) PRIMARY KEY,
    ldong_regn_cd varchar(8) NOT NULL,
    ldong_signgu_nm varchar(64) NOT NULL
);
CREATE TABLE IF NOT EXISTS lcls_systm_codes (
    lcls_systm3_cd varchar(16) PRIMARY KEY,
    lcls_systm3_nm varchar(64) NOT NULL,
    lcls_systm2_cd varchar(16),
    lcls_systm1_cd varchar(16),
    lcls_systm2_nm varchar(64),
    lcls_systm1_nm varchar(64)
);
CREATE TABLE IF NOT EXISTS spots (
    content_id varchar(32) PRIMARY KEY,
    content_type_id smallint NOT NULL,
    title varchar(255) NOT NULL,
    addr1 varchar(255),
    addr2 varchar(255),
    zipcode varchar(16),
    mapx numeric,
    mapy numeric,
    ldong_regn_cd varchar(8) REFERENCES regions(ldong_regn_cd),
    ldong_signgu_cd varchar(8) REFERENCES sigungus(ldong_signgu_cd),
    lcls_systm1 varchar(16),
    lcls_systm2 varchar(16),
    lcls_systm3 varchar(16) REFERENCES lcls_systm_codes(lcls_systm3_cd),
    cpyrht_div_cd varchar(8),
    first_image_url varchar(500),
    first_image2_url varchar(500),
    show_flag smallint NOT NULL DEFAULT 1,
    modified_time timestamptz,
    synced_at timestamptz NOT NULL DEFAULT now()
);
"""


def _ensure_test_schema(conn: psycopg.Connection) -> None:
    conn.cursor().execute(_SCHEMA)
    conn.commit()


def _cleanup(conn: psycopg.Connection) -> None:
    cur = conn.cursor()
    # sync_runs may not exist yet on a fresh DB; ignore if missing.
    cur.execute(
        "DELETE FROM spots WHERE content_id LIKE %s OR content_id = ANY(%s)",
        (TEST_PREFIX + "%", list(FIXTURE_IDS)),
    )
    cur.execute("TRUNCATE sync_runs RESTART IDENTITY")
    conn.commit()


@pytest.fixture
def db_conn():
    """Connect to pictrip_test (schema = backend Alembic head). Explicit cleanup
    before and after, because record_run/sync_daily commit mid-test."""
    conn = psycopg.connect(TEST_DSN, autocommit=False)
    # Self-bootstrap the schema (no-op on the locally-migrated DB; creates it in CI).
    _ensure_test_schema(conn)
    # Ensure sync_runs exists so TRUNCATE/DELETE never error.
    from pictrip_data.sync.audit import ensure_table

    ensure_table(conn)
    conn.commit()
    _cleanup(conn)
    try:
        yield conn
    finally:
        _cleanup(conn)
        conn.close()


@pytest.fixture
def seed_refs(db_conn):
    """Insert one region/sigungu/lcls code so FK targets exist, then COMMIT
    (so commits inside record_run/upsert can see them)."""
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES ('11','서울특별시') ON CONFLICT DO NOTHING"
    )
    cur.execute(
        "INSERT INTO sigungus (ldong_regn_cd, ldong_signgu_cd, ldong_signgu_nm) "
        "VALUES ('11','11110','종로구') ON CONFLICT DO NOTHING"
    )
    cur.execute(
        "INSERT INTO lcls_systm_codes (lcls_systm3_cd, lcls_systm3_nm) "
        "VALUES ('EV010600','문화행사') ON CONFLICT DO NOTHING"
    )
    db_conn.commit()
    return db_conn
