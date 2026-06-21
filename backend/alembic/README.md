# Alembic migrations

Backend owns **all tables except `sync_runs`** (pipeline owns that one).

Setup (when porting/initializing):
- `alembic.ini` + `env.py` (`target_metadata = Base.metadata`, `compare_type=True`).
- In `env.py`, add an `include_object` filter that **excludes `sync_runs`** so
  autogenerate never proposes to drop it (pipeline creates it via
  `CREATE TABLE IF NOT EXISTS`). See `docs/specs/admin/A01-admin-console.md` §4.

Conventions:
- Autogenerate misses partial indexes (`WHERE show_flag = 1`) and named CHECK
  constraints — **review the SQL** and hand-write them.
- Forward-only / expand→contract (see `docs/specs/platform/S10-reconcile.md`).
- Run with `POSTGRES_DB=pictrip_test`.
