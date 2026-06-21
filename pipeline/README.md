# pictrip-data (ETL pipeline)

KTO data collection for PicTrip. Runs on **CT111**, writes to the shared prod DB
(CT110 `pictrip`). Separate Python project from `backend/` — no shared venv.

## What it does

- `pictrip-data sync-daily` — daily sync of `spots` from KTO `areaBasedSyncList2`
  (watermark-based upsert + soft-delete). Runs via cron at 04:00 KST.
- Owns the **`sync_runs`** audit table (`sync/audit.py`, `CREATE TABLE IF NOT
  EXISTS`). The backend admin console reads it **read-only** — do not let backend
  Alembic manage it (see `docs/specs/admin/A01-admin-console.md` §4/§A5).
- `master/load_codes.py` — one-shot load of region/classification master codes.
- Streamlit dashboard (`dashboard/app.py`, :8501, tailnet only).

Detail/image fetches are NOT here — the backend lazy-caches those.

## Usage

```bash
uv sync
uv run pictrip-data sync-daily
uv run streamlit run src/pictrip_data/dashboard/app.py
```
