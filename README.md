# PicTrip

Image-based Korea tourism recommendation service. 2026 KTO Data Utilization
Contest — 1차 deadline **2026-09-21 16:00 KST**.

Monorepo. Design SSOT is `docs/mockups/` (16 monochrome screens). Full design
specs live in `docs/specs/` (read order S01 → S12).

## Repo layout — 5 deploy units + docs

| Path | Unit | Runtime | Deploy trigger |
|---|---|---|---|
| `backend/` | FastAPI modular monolith (+ `admin` module) | CT112 | push-to-main → GHCR → `deploy/api-host/deploy.sh` |
| `mobile/` | Expo SDK 56 RN app | EAS / stores | tag `v*` → EAS build/submit |
| `web/` | Cloudflare Pages — apex `pictrip.org` | Cloudflare | CF native Git (root = `web/`, no workflow) |
| `pipeline/` | KTO ETL CLI + Streamlit (`pictrip-data`) | CT111 | cron (daily 04:00 KST) |
| `deploy/monitoring/` | Observability stack | CT113 | docker compose |
| `docs/` | Design SSOT (specs · mockups · schema-docs · requirements) | — | not deployed |

## Topology

```
                          Internet
           ┌────────────────┴─────────────────┐
   Cloudflare Pages                    Cloudflare Tunnel
   apex pictrip.org  (web/)            api.pictrip.org → CT112:8000
   ├─ /legal/*
   ├─ /.well-known/AASA·assetlinks
   └─ /{spots|curations}/…
  ┌──────────────────── Proxmox homeserver (single node) ────────────────────┐
  │  CT112 pictrip-api      CT110 pictrip-db     CT111 pipeline   CT113 mon   │
  │  api·redis·tunnel·runner  Postgres+pgvector   pictrip-data    Prom·Grafana│
  └────────────────────────────────────────────────────────────────────────────┘
```

## Boundaries to keep (monorepo invariants)

1. **`sync_runs` is owned by `pipeline/`** (`sync/audit.py`, `CREATE TABLE IF NOT
   EXISTS`) — **never** add it to `backend/alembic/`. Backend reads it read-only.
2. **`backend/` and `pipeline/` are separate Python projects** (separate
   `pyproject.toml`/venv). Do not merge into a uv workspace — keep decoupled.
3. **admin `static/` mirrors `docs/mockups/admin/`** (UI SSOT). Copy + CI drift
   check; do not symlink (breaks Docker build).
4. **Secrets are per-directory**: backend `.env` (CT112), mobile `EXPO_PUBLIC_*`,
   web = none (link files are public), pipeline own `.env`, monitoring = Discord
   webhook. Root `.env.example` lists keys only.

## Commands

```bash
# backend (cd backend)
uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest

# mobile (cd mobile)
npm run lint && npm run typecheck && npm run format:check && npm test

# pipeline (cd pipeline)
uv run ruff check . && uv run pytest
```

See `CLAUDE.md` for full architecture, conventions, and prohibitions.
