# PicTrip

해외 여행 사진을 넘기다 마음에 드는 장면을 만나면, 스와이프 한 번으로 **닮은
분위기의 국내 관광지 3곳**을 보여준다. 텍스트 검색도, 사진 업로드도 필요 없다 —
"발견 → 매칭"이 핵심 루프다.

2026 관광데이터 활용공모전 출품작. 1차 마감 **2026-09-21 16:00 KST**.

- 국내 관광지 약 68,000곳 (KTO TourAPI)
- 해외 명소 2,347곳 (Wikidata · Wikimedia Commons)
- 매칭은 CLIP ViT-B/32 이미지 임베딩의 코사인 거리 ANN — 유사도 수치는 노출하지
  않는다(코사인 거리의 % 환산은 사용자를 오도한다)
- 여행 탭은 대화형 에이전트: LLM(`LLM_PROVIDER`, 현재 DeepSeek)이 의도를 뽑고 답변을 쓰되, **검색 자체는
  결정적 SQL/pgvector**다

## 화면

```
BootGate(스플래시) → 온보딩(최초 1회) → 탭 셸
├── 홈      해외 게시물 피드 + 상단 채널 타일 6종
├── 탐색     해외 게시물 그리드 (다크, big/side 혼합)
├── 여행     대화형 추천 — 채팅 + 지도 + 카드 캐러셀
└── 마이     프로필 · 스크랩 레일 · 설정
스택: 스팟 상세 · 스토리 뷰어 · 로그인 · 스크랩 앨범 · 설정·동의 · 약관
```

전 화면 **게스트 우선**이다. 로그인이 필요한 유일한 행동은 저장(스크랩)이고,
그 순간 루트 `AuthPromptSheet`가 떠서 로그인 성공 시 보류된 저장이 재개된다.
로그인은 kakao·apple 2종뿐 — iOS 단독 출시라 App Store 4.8이 요구하는 "동등한
대체 수단"을 Sign in with Apple이 담당한다.

화면 기준(디자인 SSOT)은 **구현된 앱**(`mobile/src`)이다. 신규 화면 디자인은
일회성 핸드오프(html 프로토타입)로 만들고 구현 후 폐기한다 — 리포에 목업을
쌓지 않는다.

## 리포 구성

| 경로 | 유닛 | 런타임 |
|---|---|---|
| `backend/` | FastAPI 모듈러 모놀리스 (+ `/admin` 콘솔) | CT112 |
| `mobile/` | Expo SDK 56 React Native 앱 | EAS / App Store |
| `web/` | Cloudflare Pages — apex `pictrip.org` | Cloudflare |
| `pipeline/` | KTO·Wikidata ETL CLI (`pictrip-data`) | CT111 |
| `workers/img-proxy/` | 이미지 프록시 Worker — `img.pictrip.org` | Cloudflare |
| `deploy/api-host/` · `deploy/monitoring/` | Ops·IaC | CT112 / CT113 |
| `docs/` | 아키텍처 · API · 결정 기록 | — |

인프라는 Proxmox 홈서버 + Cloudflare 터널이다. AWS 없음.
CT110=PostgreSQL+pgvector · CT111=pipeline · CT112=api+Redis · CT113=모니터링.

## 로컬 실행

### backend

```bash
cd backend
uv sync
cp ../.env.example .env          # KTO·Kakao·DeepSeek 키를 채운다
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

`http://127.0.0.1:8000/v1/docs` 에 OpenAPI, `/admin` 에 운영 콘솔(기본
`admin`/`admin` — `uv run python scripts/set_admin_password.py` 로 교체).

푸시 전에 전부 통과해야 한다:

```bash
uv run ruff check . && uv run ruff format --check . && \
uv run mypy app && uv run lint-imports && \
NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest
```

- `pytest`·`alembic` 은 `POSTGRES_DB=pictrip_test` 로 — 라이브 `pictrip` 행이
  전역 카운트 assert 를 깨뜨린다.
- 로컬 `pytest` 는 `NO_COLOR=1` 로 — 상속된 `FORCE_COLOR` 가 캡처 로그에 ANSI
  코드를 넣어 admin 로그 assert 를 깨뜨린다.
- 새 마이그레이션: `uv run alembic revision --autogenerate -m "..."` → **SQL 을
  직접 검토**(autogenerate 는 부분 인덱스·명명 CHECK 를 놓친다) → `upgrade head`.

### mobile

```bash
cd mobile
npm ci
cp .env.example .env             # EXPO_PUBLIC_* 만 들어간다
npx expo start
```

푸시 전에:

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```

### pipeline

```bash
cd pipeline
uv sync
uv run pictrip-data sync-daily
uv run ruff check . && uv run pytest
```

CLI 명령과 수집 DAG 는 [docs/architecture.md](docs/architecture.md#수집-dag) 참조.

## 배포

| 대상 | 트리거 | 결과 |
|---|---|---|
| backend | `dev` 머지 | GHCR 이미지 → CT112 `deploy.sh` (api.pictrip.org) |
| mobile JS | `dev` 머지 | EAS OTA — `runtimeVersion.policy: appVersion` 이라 같은 `app.json` `version` 빌드 전부에 내려간다 |
| pipeline | `dev` 머지 | CT111 rsync (`.env`·`.venv` 보존) |
| web | `main` 머지 | Cloudflare Pages (build root = `web/`) |
| iOS 빌드 | `v*` 태그 (main 에서) | EAS iOS → TestFlight |

**스테이징이 없다 — `dev` 머지가 곧 라이브다.** `main` 은 릴리스 마커다.

네이티브 모듈을 바꿨으면 OTA 로 안 나간다. `app.json` 의 `version` 을 올려
`v*` 빌드로 내야 구 빌드가 새 JS 를 받지 않는다.

## 기여

- 기본 브랜치는 `dev`. `dev` 에서 갈라 짧게 살리고 같은 날 머지한다.
- PR → `dev` → Codex 리뷰(`@codex review`) → **rebase merge**(유일하게 켜진 방식).
- **머지 전에 같은 파일을 건드리는 다른 열린 PR 이 있는지 반드시 확인한다.**
  `pr-check` 의 `overlap` 잡이 겹치는 PR 을 job summary 에 띄운다. 겹치면 먼저
  열린 PR 을 먼저 머지한다.
- PR 본문은 `.github/pull_request_template.md` 의 4개 섹션을 지켜야 required
  `template` 체크가 통과한다.

에이전트·기여자용 상세 규칙은 [`CLAUDE.md`](CLAUDE.md)(= `AGENTS.md`)에 있다.

## 문서

| 문서 | 답하는 질문 |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | 이 리포에서 코드를 어떻게 쓰나 — 규칙·금지·워크플로 |
| [`docs/architecture.md`](docs/architecture.md) | 이 시스템은 어떻게 생겼나 — 모듈·데이터·캐시·자동화 |
| [`docs/api.md`](docs/api.md) | 무엇을 호출하나 — 엔드포인트·에러 코드·화면 계약·CLI |
| [`docs/decisions.md`](docs/decisions.md) | 왜 이렇게 됐나 — 확정된 결정과 근거 |

## 라이선스·출처

- 국내 관광 데이터·이미지: 한국관광공사 TourAPI. 공공누리 `Type1`(출처표시)은
  리사이즈·포맷 변환 가능, `Type3`(변경금지)는 원본 무변형 pass-through만.
  출처 표기는 `pictrip.org/legal/data-sources` 가 전담한다.
- 해외 이미지: Wikimedia Commons — URL 참조만 하고 저작자·라이선스명·라이선스
  전문 URL·원본 파일 페이지 URL 을 함께 저장·노출한다.
- 사용자가 올린 사진은 **저장하지 않는다** — CLIP 이 메모리에서 돌고 바이트는 버린다.
