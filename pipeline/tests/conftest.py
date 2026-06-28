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
