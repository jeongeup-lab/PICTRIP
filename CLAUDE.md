# PicTrip

Image-based Korea tourism recommendation service. 2026 KTO Data Utilization
Contest — 1차 deadline **2026-09-21 16:00 KST**.

Monorepo with 5 deploy units + docs (`AGENTS.md` is a symlink to this file).
화면 기준(디자인 SSOT)은 **구현된 앱**(`mobile/src`) — 신규 화면 디자인은
일회성 핸드오프(html 프로토타입)로 만들고 구현 후 폐기한다(리포에 목업을
쌓지 않는다). 문서는 다섯 개뿐이다 — `README.md`(제품·실행·배포) · 이 파일
(규칙) · `docs/architecture.md`(구조·데이터·자동화) · `docs/api.md`(호출 계약·
어드민·CLI) · `docs/decisions.md`(살아 있는 결정). **현행만 적고 히스토리는 git이
담당한다** — 뒤집힌 결정은 지우고 근거만 새 항목에 흡수한다. 문서를 새로 만들지
말고 이 다섯 중 하나에 넣는다.

## Repo layout

| Path | Unit | Runtime |
|---|---|---|
| `backend/` | FastAPI modular monolith (+ `admin`) | CT112 |
| `mobile/` | Expo SDK 56 RN app | EAS / stores |
| `web/` | Cloudflare Pages — apex `pictrip.org` | Cloudflare |
| `pipeline/` | KTO ETL CLI (`pictrip-data`) | CT111 |
| `workers/img-proxy/` | 이미지 프록시 Worker — `img.pictrip.org` | Cloudflare |
| `deploy/api-host/` · `deploy/monitoring/` | Ops/IaC | CT112 / CT113 |
| `docs/` | architecture · api · decisions 세 문서 | — |

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
  spots · feed · images · map · admin · agent) · SQLAlchemy 2.0 async ·
  PostgreSQL + pgvector · Redis · CLIP ViT-B/32 · LLM(`LLM_PROVIDER`: **deepseek
  기본** · gemini · 로컬 codex — 2026-08-18 Gemini 크레딧 소진으로 전 구간
  DeepSeek) — agent 모듈에서 **의도 추출과 답변 작문** 둘 다 맡되 검색 자체는
  결정적 SQL/pgvector 툴이다.
- **Mobile**: Expo SDK 56 · RN 0.85 · React 19.2 · TypeScript strict · Expo
  Router (typed routes) · Zustand · TanStack Query · axios · expo-secure-store.
- **Web**: Cloudflare Pages static (legal · `.well-known` deep-link files ·
  `/spots/…` fallback pages). Build root = `web/`.
- **Pipeline**: Python CLI `pictrip-data` (KTO `areaBasedSyncList2` → `spots`
  daily sync). Owns the `sync_runs` table. 수집 이력 조회는 어드민 콘솔.
- **Infra**: Proxmox homeserver — FastAPI + Redis on CT112, Postgres on CT110,
  pipeline on CT111, monitoring on CT113. Public via Cloudflare tunnel
  `https://api.pictrip.org`. CI/CD: GitHub Actions (GHCR + self-hosted runner).
  No AWS.

## Architecture

Backend shared packages (layered, import-linter enforced: `modules` >
`security|kto|kakao|naver|ml` > `web` > `core`):

```
app/
├── core/      infra plumbing only — db · redis · logging · version
├── web/       HTTP contract — envelope (ok/err) · errors (AppError+handlers) ·
│              middleware · ratelimit
├── security/  jwt — auth deps
├── kto/       KTO API client · image-URL helpers · 필드 텍스트 정리
├── kakao/     Kakao Local API client
├── naver/     Naver 검색 API client
├── ml/        embedding — CLIP
└── modules/   domain modules (below)
```

Backend module layout (uniform per domain):

```
app/modules/<code>/
├── routes.py    HTTP I/O only — no DB, no business logic
├── services.py  business logic + transaction boundaries
├── repositories.py  (users · images · admin · feed · agent) DB queries; spots keeps
│                    its queries in services/ submodules instead
├── models.py    SQLAlchemy ORM — no business methods
└── schemas.py   Pydantic DTOs — no ORM imports
```

- Routes import services/schemas/shared packages only — never `models`/`sqlalchemy`.
- Cross-module reads go through the other module's `services.py`, never `models`.
- `admin` is the exception: read-only cross-module aggregates via its own
  `repositories.py`, plus a scoped write to `overseas_spots.is_hidden` only.
- Shared-package admission rule: only code imported by **2+ modules** goes into
  `web`/`security`/`kto`/`kakao`/`naver`/`ml`; `core` is infra plumbing only.
  Single-consumer code lives inside its module (e.g. `users/oidc.py`,
  `admin/passwords.py`). 소비자가 둘이 되는 순간 승격한다 — 안 하면 계층 역전이
  생긴다.
- `spots` 는 `services` 패키지가 유일한 공개 seam 이다. 다른 모듈이
  `spots.services.rows`·`.saved` 같은 서브모듈을 직접 import 하는 것은
  import-linter 계약이 막는다.

Mobile layers: `src/app` (thin Expo Router screens) · `src/features/<domain>`
(api/queries/stores/usecases/components/lib/hooks) · `src/lib` · `src/components` ·
`src/constants`.

Both sets of boundary rules are CI-enforced: backend via import-linter
(`uv run lint-imports`, contracts in `backend/pyproject.toml`), mobile via
ESLint `no-restricted-imports` (layer blocks in `mobile/eslint.config.js`).

## Monorepo boundaries (invariants)

- **`sync_runs` is owned by `pipeline/`** (`src/pictrip_data/sync/audit.py`,
  `CREATE TABLE IF NOT EXISTS`). Exclude it from backend Alembic autogenerate
  (`include_object`). Backend reads it read-only via raw SQL.
- **`backend/` and `pipeline/` stay separate Python projects** — no shared venv,
  no uv workspace. Only coupling = CT110 prod DB tables `spots` + `sync_runs`.
- **admin UI SSOT = `backend/app/modules/admin/static/`** — 직접 편집; 별도
  목업 사본을 두지 않는다.
- **CF Pages build root = `web/`**. `.well-known/*` needs fixed JSON
  MIME and no redirects (`web/_headers`).

## Conventions

- Every API response uses the JSend envelope `{ data, error, meta }` via `ok()`/
  `err()` (`app.web.envelope`). `traceId` auto-injected.
- Errors raise `AppError` subclasses (`app/web/errors.py`) — the subclass
  sets HTTP status. Mobile branches on `err.code`, never `err.message`.
- Settings module is `app/config.py` (`Settings(BaseSettings)`, `env_file=".env"`)
  — **not** `app/core/`. `SENTRY_DSN`/KTO/Kakao keys live here. Admin-console auth
  is **DB-backed** (`admin_users` table, not an env var) — see below.
- Admin console (`/admin`) auth = `admin_users` table (username + bcrypt
  `password_hash`), checked in `app/modules/admin/security.py`. 베이스라인
  마이그레이션이 seeds `admin`/`admin` (weak default — rotate via
  `scripts/set_admin_password.py`).
  Provisioning/rotation needs only DB write (CT110), no CT112 `.env`/shell.
- File names: components PascalCase; runtime modules (api/lib/stores/hooks/
  usecases/constants) kebab-case; `src/app/**` follows Expo Router.

## Backend DB facts (Alembic history is authoritative)

- `overview` lives on `spot_details`, not `spots` (from `detailCommon2`, cached
  90 days, verbatim). 무효화는 `spots.modified_time` 비교가 담당 — 일일 동기화가
  변경분을 올리면 그 스팟만 다시 받는다.
- Embedding columns are `halfvec(512)` (`spot_embeddings.embedding`,
  `users.taste_vector`). Cast vector literals: `... <=> $1::halfvec(512)`.
- 연관 관광지(agent `related` 앵커)는 KTO TarRlteTar 가 아니라 `spot_embeddings`
  이웃 검색이다 (`agent/services/anchor.py`). 임베딩이 없는 스팟은
  `AgentNoResults` 로 실패한다. 구 `rlte:{contentId}` Redis 캐시는 제거됨.
- `hnsw.ef_search = 80` is an asyncpg `server_settings` in `app/core/db.py`.
- 해외 게시물 피드는 `GET /explore` 하나다(홈·탐색이 같은 문을 쓴다): 커서
  페이지네이션 + 국내 매칭 3곳을 `items[].matches` 로 같이 싣는다(왕복 1회).
  `/feed` 는 `/explore` 의 deprecated 별칭으로만 남는다 — OTA 를 못 받는 v0.6.0
  빌드가 아직 친다(만료 2026-10-13 후 삭제). 구 `/home/feed`·`/curations/{slug}`·
  `/taste/photo-search`는 제거됐고
  `curations`/`curation_spots` 테이블도 리비전 `0026`에서 DROP 했다. 아직 남은
  은퇴 테이블(`plans`·`travel_shorts`·`travel_shorts_spots`)은 ORM이 없으므로
  `include_object` 제외가 유일한 보호막이다.
- `overseas_spots`는 **백엔드 Alembic 소유**, 행 적재는
  `pipeline/` Wikidata ETL. 매칭은 `overseas_spot_matches`에 사전계산한다
  (`scripts.precompute_matches`, PK `(overseas_id, rank)`, rank 1–3). 저장은
  `content_id`뿐이고 표시 필드는 읽을 때 `spots` 라이브 조인 — 구 Redis
  `match:{revision}:{overseasId}` 캐시는 제거됐다.
- `spot_concentration`은 `pipeline-daily.yml` 의 `concentration` 잡이 적재 —
  Hot/Hidden 채널(`/home/channels`) 소스.
- Auth = denylist-only: `denyjti:{jti}` in Redis, fail-open. No session/device
  tables, no refresh rotation. access=memory, refresh=expo-secure-store.
  로그인은 kakao·apple 2종뿐(iOS 단독 출시 · App Store 4.8). 애플은 로그인 시
  `authorizationCode`로 refresh token을 교환해 `user_auth_providers.provider_refresh_token`
  에 넣고, 탈퇴 시 Apple `/auth/revoke`를 부른다(실패해도 탈퇴는 진행 — 베스트에포트).

## Prohibitions

- **KTO 이미지 프록시/CDN 캐싱 허용** — 2026-07-16 공모전 운영사무국 확인으로 구
  "다운로드·재호스팅 금지" 조항 폐기 (구 조항은 콘텐츠랩 파일데이터 규정과 이미지
  규정을 혼동한 것 — 2026 설명회·OT자료 원문 재분석으로 확인). 경계는 공공누리
  라이선스: `cpyrhtDivCd=Type1`(출처표시)은 리사이즈·포맷 변환 가능, `Type3`
  (변경금지)는 **원본 무변형 pass-through만**. 출처(한국관광공사) 표기 유지.
- **DO NOT persist user-uploaded images** — CLIP runs in memory, bytes discarded.
- **Wikimedia Commons images: URL only + 표기 의무** — 저작자·라이선스명에 더해
  라이선스 전문 URL·원본 파일 페이지 URL을 저장·노출한다.
- **DO NOT modify KTO `overview` text** — store and display verbatim.
- **DO NOT put secrets in code or commits** — `.env` only; mobile gets only
  `EXPO_PUBLIC_*`.
- **DO NOT add emoji to mobile** — use line-SVG `<Icon>` / `expo-symbols`.
  Map = KakaoWebMap (WebView + JS SDK), never `@react-native-kakao/map`.
- 네이티브 모듈 추가는 허용한다 — Expo SDK 56 호환 여부를 먼저 확인하고,
  추가하면 OTA 로는 안 나가므로 `app.json` `version` 을 올려 `v*` 빌드로 낸다.
- **DO NOT add `sync_runs` to backend Alembic** — pipeline owns it.
- **엔드포인트를 지우기 전에 "배포된 빌드"를 기준으로 재라** — 현재 `mobile/src`
  에서 호출 0건인 것과, 살아 있는 빌드가 안 부르는 것은 다르다. `runtimeVersion.
  policy: appVersion` 이라 구 `v*` 빌드는 OTA 를 영영 못 받는다. 확인은 태그별로:
  ```bash
  git tag -l 'v*'
  git grep -hoE "['\"\`]/[a-z][a-z0-9/{}$-]*" <tag> -- 'mobile/src/**/*.ts*'
  ```
  살아 있는 빌드가 부르면 지우지 말고 `deprecated=True` 별칭으로 남기고, 삭제
  조건(빌드 만료일)을 docstring 에 적는다.
- **`#` / `//` 주석 금지** — 의도는 이름·구조로 드러내고, 문맥은 커밋 메시지/PR에
  남긴다. (shebang·라이선스 헤더, raw SQL 안의 `--`, 설정 파일은 예외.)
- **docstring 은 "왜"에만 쓴다** — 모듈 최상단 한 줄(이 파일의 책임)과, 이름으로
  드러나지 않는 결정·실측 근거만. `Args:`/`Returns:`/`Raises:` 섹션 금지 — 타입
  힌트가 정본이고 mypy strict 가 보증한다. 판정 시험: *"이름을 더 좋게 고치면 이
  docstring 이 필요 없어지나?"* → 예면 이름을 고치고 docstring 을 지운다.
  형식은 ruff `D` 가 검사한다(필수화 규칙 D1xx 는 꺼 둔다 — 다는 게 기본이 아니다).

## Review guidelines

Automated PR review (Codex GitHub connector reads this section via the
`AGENTS.md` symlink). Comment in Korean; flag only real problems inline and
skip minor style nits. Focus on:

- Correctness bugs and clear logic errors.
- Module-boundary violations: `routes.py` importing DB/models/sqlalchemy, or
  cross-module access to another module's `models` instead of its `services.py`.
- Monorepo invariants: `sync_runs` is pipeline-owned (never in backend Alembic),
  backend/pipeline stay separate Python projects.
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
- **머지 전에 같은 파일을 건드리는 다른 열린 PR이 있는지 반드시 확인한다.** 이건
  팀 여러 명 + 에이전트가 같은 파일을 동시에 고치는 리포다. 모르고 먼저 머지하면
  상대 PR이 그 자리에서 충돌 상태가 된다 (실제 사고: #213을 머지해서 먼저 열려
  있던 #212가 `feed/components` 3개 파일에서 깨졌다 — 머지 직전까지 충돌 0건이었다).
  `pr-check`의 `overlap` 잡이 겹치는 PR을 job summary에 띄우니 머지 전에 읽을 것.
  수동 확인은 아래 한 줄:
  ```bash
  gh pr view <내PR> --json files -q '.files[].path' | sort > /tmp/mine
  gh pr list --state open --base dev --json number,title,author -q '.[]|"\(.number) \(.title)"'
  gh pr view <상대PR> --json files -q '.files[].path' | sort | comm -12 - /tmp/mine
  ```
  겹치면 **먼저 열린 PR을 먼저 머지**하거나 저자와 순서를 맞춘다. 내 변경이 더
  작으면 상대 PR이 들어간 뒤 그 위에 다시 얹는 쪽이 싸다.
- Merging to `dev` deploys automatically: backend → CT112 (api.pictrip.org),
  mobile → EAS OTA (JS-only; `runtimeVersion.policy: appVersion` 이라 같은
  `app.json` `version` 빌드 전부에 내려간다 — 네이티브를 바꿨으면 `version` 을
  올려야 구 빌드가 새 JS 를 받지 않는다), pipeline → CT111. **There is no staging — a dev merge is
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
