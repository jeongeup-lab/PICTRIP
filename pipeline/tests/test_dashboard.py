from pictrip_data.dashboard.app import recent_runs
from pictrip_data.sync.audit import ensure_table, record_run


def test_recent_runs_returns_rows(db_conn):
    ensure_table(db_conn)
    with record_run(db_conn, "daily") as c:
        c["fetched"] = 3
    rows = recent_runs(db_conn, limit=10)
    assert rows and rows[0]["status"] == "success"
    assert rows[0]["fetched"] == 3
