import psycopg

from pictrip_data.config import settings

_COLS = [
    "id",
    "status",
    "mode",
    "started_at",
    "finished_at",
    "api_calls",
    "fetched",
    "inserted",
    "updated",
    "soft_deleted",
    "skipped",
    "duration_sec",
    "error",
]


def recent_runs(conn: psycopg.Connection, limit: int = 50) -> list[dict]:
    cur = conn.cursor()
    cur.execute(f"SELECT {', '.join(_COLS)} FROM sync_runs ORDER BY id DESC LIMIT %s", (limit,))
    return [dict(zip(_COLS, row)) for row in cur.fetchall()]


def main() -> None:  # pragma: no cover - Streamlit entrypoint
    import streamlit as st

    st.title("pictrip-data — pipeline dashboard")
    st.caption("KTO collection runs (sync_runs). Internal / tailnet only.")
    with psycopg.connect(settings.database_url) as conn:
        rows = recent_runs(conn)
    st.dataframe(rows)
    errors = [r for r in rows if r["status"] == "error"]
    if errors:
        st.subheader("Recent errors")
        for r in errors:
            st.error(f"run {r['id']}: {r['error']}")


if __name__ == "__main__":  # pragma: no cover
    main()
