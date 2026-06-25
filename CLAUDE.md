# PicTrip

Image-based Korea tourism recommendation service. 2026 KTO Data Utilization
Contest — 1차 deadline **2026-09-21 16:00 KST**.

Monorepo with 5 deploy units + docs (`AGENTS.md` is a symlink to this file).
Design SSOT is `docs/mockups/` (16 monochrome screens). Full specs in
`docs/specs/` (read order S01 → S12); `docs/specs/_context/session-context.md`
holds the locked decisions.

## Repo layout

| Path | Unit | Runtime |
|---|---|---|
| `backend/` | FastAPI modular monolith (+ `admin`) | CT112 |
| `mobile/` | Expo SDK 56 RN app | EAS / stores |
| `web/` | Cloudflare Pages — apex `pictrip.org` | Cloudflare |
| `pipeline/` | KTO ETL CLI + Streamlit (`pictrip-data`) | CT111 |
| `deploy/api-host/` · `deploy/monitoring/` | Ops/IaC | CT112 / CT113 |
| `admin/` | Admin console specs · mockups · status (code lives in `backend/app/modules/admin/`) | — |
| `docs/` | Design + spec SSOT | — |

## Commands

```bash
# Backend (cd backend) — run all before pushing
uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest

# Mobile (cd mobile) — run all before pushing
npm run lint && npm run typecheck && npm run format:check && npm test

# Pipeline (cd pipeline)
uv run ruff check . && uv run pytest
```

- Run backend `pytest`/`alembic` with `POSTGRES_DB=pictrip_test` (live `pictrip`
  rows break global-count asserts).
- New migration: `uv run alembic revision --autogenerate -m "..."`, then **review
  the SQL** (autogenerate misses indexes/CHECK constraints), then `alembic upgrade head`.

## Stack

- **Backend**: Python 3.12 · FastAPI modular monolith (`app/modules/`: users ·
  taste · spots · images · map · system · admin) · SQLAlchemy 2.0 async ·
  PostgreSQL + pgvector · Redis · CLIP ViT-B/32 · Claude Haiku.
- **Mobile**: Expo SDK 56 · RN 0.85 · React 19.2 · TypeScript strict · Expo
  Router (typed routes) · Zustand · TanStack Query · axios · expo-secure-store.
- **Web**: Cloudflare Pages static (legal · `.well-known` deep-link files ·
  `/{spots|curations}/…` fallback pages). Build root = `web/`.
- **Pipeline**: Python CLI `pictrip-data` (KTO `areaBasedSyncList2` → `spots`
  daily sync) + Streamlit dashboard. Owns the `sync_runs` table.
- **Infra**: Proxmox homeserver — FastAPI + Redis on CT112, Postgres on CT110,
  pipeline on CT111, monitoring on CT113. Public via Cloudflare tunnel
  `https://api.pictrip.org`. CI/CD: GitHub Actions (GHCR + self-hosted runner).
  No AWS.

## Architecture

Backend module layout (uniform per domain):

```
app/modules/<code>/
├── routes.py    HTTP I/O only — no DB, no business logic
├── services.py  business logic + transaction boundaries
├── repositories.py  (spots, admin only) DB queries; SQLAlchemy lives here
├── models.py    SQLAlchemy ORM — no business methods
└── schemas.py   Pydantic DTOs — no ORM imports
```

- Routes import services/schemas/`app.core.*` only — never `models`/`sqlalchemy`.
- Cross-module reads go through the other module's `services.py`, never `models`.
- `admin` is the exception: read-only cross-module aggregates via its own
  `repositories.py`, plus scoped writes to `curations`/`curation_spots` only.

Mobile layers: `src/app` (thin Expo Router screens) · `src/features/<domain>`
(api/queries/stores/usecases/components) · `src/lib` · `src/components` · `src/constants` · `src/hooks`.

## Monorepo boundaries (invariants)

- **`sync_runs` is owned by `pipeline/`** (`src/pictrip_data/sync/audit.py`,
  `CREATE TABLE IF NOT EXISTS`). Exclude it from backend Alembic autogenerate
  (`include_object`). Backend reads it read-only via raw SQL.
- **`backend/` and `pipeline/` stay separate Python projects** — no shared venv,
  no uv workspace. Only coupling = CT110 prod DB tables `spots` + `sync_runs`.
- **admin `static/` is a copy of `admin/mockups/`** (UI SSOT) + CI drift
  check; not a symlink.
- **CF Pages build root = `web/`** (S08 §5.2). `.well-known/*` needs fixed JSON
  MIME and no redirects (`web/_headers`).

## Conventions

- Every API response uses the JSend envelope `{ data, error, meta }` via `ok()`/
  `err()` (`app.core.schemas`). `traceId` auto-injected.
- Errors raise `AppError` subclasses (`app/core/exceptions.py`) — the subclass
  sets HTTP status. Mobile branches on `err.code`, never `err.message`.
- Settings module is `app/config.py` (`Settings(BaseSettings)`, `env_file=".env"`)
  — **not** `app/core/`. `ADMIN_PASSWORD`/`SENTRY_DSN`/KTO/Kakao keys live here.
- File names: components PascalCase; runtime modules (api/lib/stores/hooks/
  usecases/constants) kebab-case; `src/app/**` follows Expo Router.

## Backend DB facts (Alembic history is authoritative)

- `overview` lives on `spot_details`, not `spots` (from `detailCommon2`, cached
  7 days, verbatim).
- Embedding columns are `halfvec(512)` (`spot_embeddings.embedding`,
  `users.taste_vector`). Cast vector literals: `... <=> $1::halfvec(512)`.
- Related-spots (TarRlteTar) are Redis-only: key `rlte:{contentId}`, TTL 1h.
- `hnsw.ef_search = 80` is an asyncpg `server_settings` in `app/core/db.py`.
- Curation is a first-class entity: `curations` + `curation_spots`. Home feed
  (`/home/feed`) is backend-assembled (hero 6 + mood rails 3).
- Auth = denylist-only: `denyjti:{jti}` in Redis, fail-open. No session/device
  tables, no refresh rotation. access=memory, refresh=expo-secure-store.

## Prohibitions

- **DO NOT download or store KTO images** — URLs only (`cpyrhtDivCd Type3`).
- **DO NOT persist user-uploaded images** — CLIP runs in memory, bytes discarded.
- **DO NOT modify KTO `overview` text** — store and display verbatim.
- **DO NOT put secrets in code or commits** — `.env` only; mobile gets only
  `EXPO_PUBLIC_*`.
- **DO NOT add emoji or new native modules to mobile** — use line-SVG `<Icon>` /
  `expo-symbols`. Map = KakaoWebMap (WebView + JS SDK), never `@react-native-kakao/map`.
- **DO NOT add `sync_runs` to backend Alembic** — pipeline owns it.

## Workflow

- Branch off `main`; short-lived, merge same-day. Commit/push only when asked.
- Record load-bearing decisions in the PR description.
- Verify against current code before asserting a fact — these docs drift.
