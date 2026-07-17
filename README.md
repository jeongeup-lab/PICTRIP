# PicTrip

해외 여행 사진을 구경하다 마음에 드는 장면을 발견하면, **닮은 분위기의 국내
관광지 3곳**을 찾아주는 이미지 기반 여행 추천 앱. 한국관광공사(KTO) TourAPI
데이터 위에 CLIP 이미지 임베딩 매칭으로 동작한다 (LLM 미사용).

2026 관광데이터 활용공모전 출품작 — 1차 마감 **2026-09-21**.

## 구성

| 경로 | 유닛 | 스택 | 배포 |
|---|---|---|---|
| `backend/` | API 서버 (+어드민 콘솔) | FastAPI · SQLAlchemy async · PostgreSQL+pgvector · Redis · CLIP | CT112 · [api.pictrip.org](https://api.pictrip.org/health) |
| `mobile/` | iOS/Android 앱 | Expo SDK 56 · RN 0.85 · TypeScript | TestFlight (`v*` 태그) + EAS OTA |
| `web/` | 랜딩·legal·딥링크 | Cloudflare Pages 정적 | [pictrip.org](https://pictrip.org) |
| `pipeline/` | KTO/Wikidata ETL | Python CLI `pictrip-data` + Streamlit | CT111 |
| `deploy/` | IaC·모니터링 | Docker Compose · Prometheus | CT112/CT113 |
| `admin/` | 어드민 UI 소스(mockups) | 정적 HTML/JS → backend가 서빙 | — |

인프라는 Proxmox 홈서버(LXC 4대) + Cloudflare 터널/Pages/Worker. AWS 없음.

## 빠른 시작

```bash
# Backend
cd backend && uv sync && uv run uvicorn app.main:app --reload
uv run ruff check . && uv run mypy app && uv run lint-imports && uv run pytest   # 푸시 전 필수

# Mobile
cd mobile && npm install && npx expo start
npm run lint && npm run typecheck && npm run format:check && npm test           # 푸시 전 필수

# Pipeline
cd pipeline && uv sync && uv run pictrip-data --help
```

로컬 백엔드는 `.env`의 Postgres/Redis를 바라본다. 테스트는 반드시
`POSTGRES_DB=pictrip_test`로 실행한다.

## 문서

| 문서 | 답하는 질문 |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | 개발 규칙·아키텍처 경계·금지사항 (에이전트/리뷰어 헌법) |
| [`docs/product.md`](docs/product.md) | 제품이 무엇인가 — 화면·플로우·기능 |
| [`docs/architecture.md`](docs/architecture.md) | 어떻게 생겼나 — API·DB·캐시·외부 연동 |
| [`docs/operations.md`](docs/operations.md) | 어떻게 돌리나 — 배포·크론·runbook·시크릿 |
| [`docs/decisions.md`](docs/decisions.md) | 왜 이렇게 만들었나 — 결정 로그 (append-only) |

## 데이터 출처

관광지 정보·이미지: **한국관광공사 TourAPI** (공공누리 유형별 표시).
해외 스팟 이미지: **Wikimedia Commons** (저작자·라이선스·원본 링크 표기).
