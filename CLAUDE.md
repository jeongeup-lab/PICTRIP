# PicTrip

Image-based Korea tourism recommendation service. 2026 KTO Data Utilization
Contest — 1차 deadline **2026-09-21 16:00 KST**.

Monorepo with 5 deploy units + docs (`AGENTS.md` is a symlink to this file).
화면 기준(디자인 SSOT)은 **구현된 앱**(`mobile/src`) — 신규 화면 디자인은
일회성 핸드오프(html 프로토타입)로 만들고 구현 후 폐기한다(리포에 목업을
쌓지 않는다; `admin/mockups/`만 예외 — 어드민 UI의 소스다). Full specs in
`docs/specs/` (flat, stable IDs `S00`–`S13`, sort order = read order);
`docs/specs/DECISIONS.md` holds the locked decisions.

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
uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run lint-imports && uv run pytest

# Mobile (cd mobile) — run all before pushing
npm run lint && npm run typecheck && npm run format:check && npm test

# Pipeline (cd pipeline)
uv run ruff check . && uv run pytest
```

- Run backend `pytest`/`alembic` with `POSTGRES_DB=pictrip_test` (live `pictrip`
  rows break global-count asserts).
- Run local `pytest` with `NO_COLOR=1` — an inherited `FORCE_COLOR` injects ANSI
  codes into captured logs and breaks the admin log asserts.
- New migration: `uv run alembic revision --autogenerate -m "..."`, then **review
  the SQL** (autogenerate misses indexes/CHECK constraints), then `alembic upgrade head`.

## Stack

- **Backend**: Python 3.12 · FastAPI modular monolith (`app/modules/`: users ·
  spots · feed · images · map · system · admin) · SQLAlchemy 2.0 async ·
  PostgreSQL + pgvector · Redis · CLIP ViT-B/32 (LLM 미사용 — S13).
- **Mobile**: Expo SDK 56 · RN 0.85 · React 19.2 · TypeScript strict · Expo
  Router (typed routes) · Zustand · TanStack Query · axios · expo-secure-store.
- **Web**: Cloudflare Pages static (legal · `.well-known` deep-link files ·
  `/spots/…` fallback pages). Build root = `web/`.
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
├── repositories.py  (map · users · images · admin · feed) DB queries; spots keeps
│                    its queries in services/ submodules instead
├── models.py    SQLAlchemy ORM — no business methods
└── schemas.py   Pydantic DTOs — no ORM imports
```

- Routes import services/schemas/`app.core.*` only — never `models`/`sqlalchemy`.
- Cross-module reads go through the other module's `services.py`, never `models`.
- `admin` is the exception: read-only cross-module aggregates via its own
  `repositories.py`, plus a scoped write to `overseas_spots.is_hidden` only.
- `app/core/` admission rule: infrastructure plumbing (db, redis, auth,
  middleware, logging, envelope, errors) or utilities imported by **2+ modules**
  (`embedding`, `passwords`, `kto_client`, `kto_images`). Single-consumer code
  lives inside its module (e.g. `users/oidc.py`, `map/kakao_local.py`) — don't
  park it in core.

Mobile layers: `src/app` (thin Expo Router screens) · `src/features/<domain>`
(api/queries/stores/usecases/components) · `src/lib` · `src/components` · `src/constants` · `src/hooks`.

Both sets of boundary rules are CI-enforced: backend via import-linter
(`uv run lint-imports`, contracts in `backend/pyproject.toml`), mobile via
ESLint `no-restricted-imports` (layer blocks in `mobile/eslint.config.js`).

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
  — **not** `app/core/`. `SENTRY_DSN`/KTO/Kakao keys live here. Admin-console auth
  is **DB-backed** (`admin_users` table, not an env var) — see below.
- Admin console (`/admin`) auth = `admin_users` table (username + bcrypt
  `password_hash`), checked in `app/modules/admin/security.py`. Migration 0016
  seeds `admin`/`admin` (weak default — rotate via `scripts/set_admin_password.py`).
  Provisioning/rotation needs only DB write (CT110), no CT112 `.env`/shell.
- File names: components PascalCase; runtime modules (api/lib/stores/hooks/
  usecases/constants) kebab-case; `src/app/**` follows Expo Router.

## Backend DB facts (Alembic history is authoritative)

- `overview` lives on `spot_details`, not `spots` (from `detailCommon2`, cached
  7 days, verbatim).
- Embedding columns are `halfvec(512)` (`spot_embeddings.embedding`,
  `users.taste_vector`). Cast vector literals: `... <=> $1::halfvec(512)`.
- Related-spots (TarRlteTar) are Redis-only: key `rlte:{contentId}`, TTL 1h.
- `hnsw.ef_search = 80` is an asyncpg `server_settings` in `app/core/db.py`.
- Home feed is `GET /feed` (S13): 해외 게시물 커서 페이지네이션 → 스와이프 시
  `GET /overseas/{id}/matches`로 국내 매칭 3곳. 구 `/home/feed`(히어로+레일)·
  `/curations/{slug}`·`/taste/photo-search`는 제거 — `curations`/`curation_spots`
  테이블은 잔존(서빙 표면·ORM 모델 없음; autogenerate에서 `include_object`로 제외).
- `overseas_spots`는 **백엔드 Alembic 소유**(마이그레이션 0018), 행 적재는
  `pipeline/` Wikidata ETL. 매칭 캐시는 Redis `match:{revision}:{overseasId}`
  (TTL 6h, `matching:revision`으로 무효화).
- `spot_concentration`은 일일 크론 적재(`concentration-sync.yml`, 04:30 KST) —
  Hot/Hidden 채널(`/home/channels`) 소스.
- Auth = denylist-only: `denyjti:{jti}` in Redis, fail-open. No session/device
  tables, no refresh rotation. access=memory, refresh=expo-secure-store.

## Prohibitions

- **KTO 이미지 프록시/CDN 캐싱 허용** — 2026-07-16 공모전 운영사무국 확인으로 구
  "다운로드·재호스팅 금지" 조항 폐기 (구 조항은 콘텐츠랩 파일데이터 규정과 이미지
  규정을 혼동한 것 — 2026 설명회·OT자료 원문 재분석으로 확인). 경계는 공공누리
  라이선스: `cpyrhtDivCd=Type1`(출처표시)은 리사이즈·포맷 변환 가능, `Type3`
  (변경금지)는 **원본 무변형 pass-through만**. 출처(한국관광공사) 표기 유지.
- **데이터 소스는 OpenAPI 호출이어야 한다** — 콘텐츠랩 파일데이터·맞춤형 데이터
  다운로드를 데이터 소스로 쓰면 공모전에서 OpenAPI 활용으로 **인정되지 않는다**
  (2026 OT자료 1차 심사 유의사항·설명회 슬라이드 3).
- **DO NOT persist user-uploaded images** — CLIP runs in memory, bytes discarded.
- **Wikimedia Commons images: URL only + 표기 의무** — 저작자·라이선스명에 더해
  라이선스 전문 URL·원본 파일 페이지 URL을 저장·노출한다 (S13 §5.4·§7.1).
- **DO NOT modify KTO `overview` text** — store and display verbatim.
- **DO NOT put secrets in code or commits** — `.env` only; mobile gets only
  `EXPO_PUBLIC_*`.
- **DO NOT add emoji or new native modules to mobile** — use line-SVG `<Icon>` /
  `expo-symbols`. Map = KakaoWebMap (WebView + JS SDK), never `@react-native-kakao/map`.
- **DO NOT add `sync_runs` to backend Alembic** — pipeline owns it.
- **DO NOT write code comments** — 코드에 주석을 달지 않는다. 의도는 이름·구조로
  드러내고, 문맥은 커밋 메시지/PR에 남긴다. (shebang·라이선스 헤더 등 도구가 요구하는
  줄은 예외.)

## Review guidelines

Automated PR review (Codex GitHub connector reads this section via the
`AGENTS.md` symlink). Comment in Korean; flag only real problems inline and
skip minor style nits. Focus on:

- Correctness bugs and clear logic errors.
- Module-boundary violations: `routes.py` importing DB/models/sqlalchemy, or
  cross-module access to another module's `models` instead of its `services.py`.
- Monorepo invariants: `sync_runs` is pipeline-owned (never in backend Alembic),
  backend/pipeline stay separate Python projects, admin `static/` must be a
  byte-identical copy of `admin/mockups/`.
- JSend envelope (`ok()`/`err()`) and `AppError` subclasses — mobile must branch
  on `err.code`, never `err.message`.
- KTO compliance (see Prohibitions): `cpyrhtDivCd=Type3` 이미지 변형(리사이즈 등)
  금지·출처표시 유지, no persisted user uploads, `overview` text verbatim, no
  secrets in code.

## Workflow

- Default branch is `dev`. Branch off `dev`; short-lived, merge same-day.
  Commit/push only when asked.
- PR flow: feature branch → PR to `dev` → address Codex review → **rebase
  merge** (the only enabled merge method — keep PR commits clean, no WIP/fixup
  noise).
- Merging to `dev` deploys automatically: backend → CT112 (api.pictrip.org),
  mobile → EAS OTA (JS-only; native changes are silently skipped by the
  fingerprint guard), pipeline → CT111. **There is no staging — a dev merge is
  live.**
- `main` is the release marker: dev → main PR at milestones. `v*` tags
  (TestFlight builds via mobile-deploy) are cut from main; web (CF Pages)
  also builds from main.
- PR body must follow `.github/pull_request_template.md` — `## 요약` / `## 변경
  단위` / `## 핵심 결정` / `## 검증` sections, with ≥1 checked box in 변경 단위
  and 검증 — or the required `template` check fails.
- PR body style — write for skimming:
  - 요약 = 불릿 2~4개, 각 1~2줄, 사실 하나씩. 문단으로 시작하지 않기.
  - 괄호 중첩·긴 인과 서사 문장 금지 — 문장을 끊고, 결론 먼저.
  - 구체 예시·숫자를 붙이기 (`70s → 0.2s`, `예: "통영 중앙로 100"`).
  - 핵심 결정 = **결정 볼드 1줄** + 근거 1~2문장. 문단 금지.
- Record load-bearing decisions in the PR description.
- Verify against current code before asserting a fact — these docs drift.
