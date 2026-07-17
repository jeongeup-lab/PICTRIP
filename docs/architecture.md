# 아키텍처 레퍼런스 (API · DB · 캐시)

> 갱신: 2026-07-17 (alembic head `0020`) · **코드가 SSOT** — 이 문서는 지도다.
> 라우트는 `backend/app/modules/*/routes.py`, 스키마는 Alembic 히스토리가 정본.

## 백엔드 모듈 구조

```
app/modules/<code>/          users · spots · feed · images · map · system · admin
├── routes.py      HTTP I/O만 — DB·비즈니스 로직 금지
├── services.py    비즈니스 로직 + 트랜잭션 경계
├── repositories.py  DB 쿼리 (spots는 services/ 하위 모듈에 보관)
├── models.py      SQLAlchemy ORM
└── schemas.py     Pydantic DTO
```

경계는 import-linter가 CI 강제. 교차 모듈 읽기는 상대 모듈 `services.py` 경유
(admin만 예외: read-only 집계 + `overseas_spots.is_hidden` 한정 쓰기).
모든 응답은 JSend `{data, error, meta}` (`ok()`/`err()`), 에러는 `AppError`
서브클래스가 HTTP 상태를 결정하고 모바일은 `err.code`로만 분기한다.

## 공개 API (`/v1`)

| Method | Path | 목적 | 인증 |
|---|---|---|---|
| POST | `/auth/oauth/{provider}` | OIDC id_token → 토큰쌍 (kakao·google·apple) | — |
| POST | `/auth/email/signup` · `/auth/email/login` | 이메일 가입/로그인 (rate-limit 5·10/분) | — |
| POST | `/auth/refresh` | 슬라이딩 재발급 (denylist 확인) | refresh 본문 |
| POST | `/auth/logout` | 멱등 로그아웃 (jti denylist) | — |
| GET/DELETE | `/users/me` | 프로필 / 탈퇴(익명화) | JWT |
| GET/PUT | `/users/me/consents` | 동의 상태(위치·사진·약관) | JWT |
| GET | `/users/me/saved` | 저장 목록 (커서) | JWT |
| POST/DELETE | `/users/me/saved/{contentId}` | 저장/해제 (멱등) | JWT |
| GET | `/spots/{contentId}` | 스팟 상세 (KTO lazy fetch + 7일 캐시) | — |
| GET | `/feed` | 홈 피드 — 해외 게시물 (seed+cursor, 6개) | — |
| GET | `/explore` | 탐색 그리드 (동일 소스, 30개) | — |
| GET | `/overseas/{id}/matches` | 해외→국내 매칭 3곳 (ANN + Redis 캐시) | — |
| GET | `/home/channels` · `/home/channels/{key}` | 채널 메타 / 카드 (hot·hidden·festa·snap·pets) | — |
| GET | `/map/nearby` | 내 주변 (bbox+haversine, 카테고리) | — |
| GET | `/map/region` | 좌표→행정구역 라벨 (Kakao, fail-open null) | — |
| GET | `/map/regions-tree` | 시도·시군구 트리 (런타임 centroid, 24h 캐시) | — |
| GET | `/meta/version` | 버전·환경·ktoApiStatus | — |
| GET | `/health` (루트) | liveness | — |

어드민 콘솔은 `/v1` 밖 `/admin` (서명 쿠키 세션, `admin_users` 테이블 인증):
페이지 4종(개요·이력·헬스·해외 숨김) + `/admin/api/*` (수집 상태·트리거,
임베딩 상태·재임베딩 트리거, 이력 롤업, 컴포넌트 헬스, overseas 목록·
`is_hidden` 토글). `images` 모듈은 공개 엔드포인트 0 (임베딩 잡·모델 전용).

## 에러 코드

`app/core/exceptions.py`가 정본. 자주 쓰는 것: `AUTH_TOKEN_EXPIRED`(401 → 모바일이
silent refresh), `GUEST_FORBIDDEN`(403 → 로그인 시트), `RESOURCE_NOT_FOUND`(404),
`RATE_LIMITED`(429), `KTO_API_UNAVAILABLE`(502 → 부분 화면 degrade),
`EMAIL_TAKEN`(409) · `AUTH_INVALID_CREDENTIALS`(401) · `AUTH_SESSION_REVOKED`(401),
admin 전용 `ADMIN_*` 4종. 전체 코드 union은 `mobile/src/lib/app-error.ts`와
동기 — **새 코드 추가 시 양쪽을 함께 갱신**한다.

## DB (PostgreSQL + pgvector, CT110)

스키마 소유는 전부 backend Alembic (예외: `sync_runs` = pipeline 소유,
`CREATE TABLE IF NOT EXISTS`). "적재" 열은 데이터를 쓰는 주체.

| 테이블 | 적재 | 요지 |
|---|---|---|
| `spots` | pipeline (일일 sync) | KTO 스팟 마스터. `show_flag=1` partial index 다수, `cpyrht_div_cd` CHECK(Type1/Type3) |
| `spot_details` | backend (lazy) | detail* 7일 캐시. **`overview`는 여기 있고 verbatim** |
| `spot_images` | backend (lazy) | detailImage2 URL만 (bytes 금지) |
| `spot_embeddings` | backend 잡 | 대표사진 CLIP `halfvec(512)` + HNSW(halfvec_cosine) |
| `spot_embeddings_gallery` | backend 잡 (일 800) | 갤러리 최대 5장 centroid. 0020 트리거가 이미지 변경 시 행 삭제 |
| `embedding_failures` | backend 잡 | 임베딩 실패 백로그 (`--only-failed` 재시도 큐) |
| `overseas_spots` | pipeline (월간 Wikidata ETL) | 해외 게시물 원천. `wikidata_id` unique, `fame_score`, `is_hidden`(admin 토글), embedding HNSW |
| `spot_concentration` | 일일 크론 | 집중률 — Hot/Hidden 채널 소스 |
| `users` / `user_auth_providers` / `user_consents` / `user_saved_spots` | backend | `taste_vector halfvec(512)`, provider CHECK(email 포함), 저장은 (user,content) PK |
| `admin_users` | 수동 | 콘솔 자격증명 (bcrypt) |
| `moods` · `spot_moods` · `regions` · `sigungus` · `lcls_systm_codes` | 시드/pipeline | 마스터 코드 |
| `sync_runs` | **pipeline 소유** | backend는 raw SQL read-only. **backend Alembic에 절대 추가 금지** |
| `curations` · `curation_spots` | — | 은퇴 자산. ORM 없음, autogenerate `include_object` 제외로 보존 |

벡터 리터럴 캐스팅: `... <=> $1::halfvec(512)`. `hnsw.ef_search=80`은
`app/core/db.py`의 asyncpg `server_settings`.

## Redis 키

| 패턴 | TTL | 용도 |
|---|---|---|
| `denyjti:{jti}` | refresh 잔여 수명 | 로그아웃/탈퇴 denylist (**fail-open**) |
| `rl:{bucket}:{ip}` | 60s | rate-limit 카운터 (fail-open) |
| `spotdetail:v1:{contentId}` | 1h | 상세 응답 hot front |
| `rlte:{contentId}` | 1h | 연관 관광지 (Redis 전용, 테이블 없음) |
| `match:{revision}:{overseasId}` | 6h | 매칭 결과. `matching:revision` incr로 전체 무효화 |
| `channel:{key}:{version}` | KTO 채널 3일 / 집중률 채널 1h | 홈 채널 카드 |
| `region:{lat:.3f}:{lng:.3f}` | 1일 | Kakao 역지오코딩 (null 캐시 포함) |
| `regions:tree` | 24h | 시도·시군구 트리 |
| `admin:embed:running` | 4h | 재임베딩 잡 분산 락 (SET NX) |

영속성 AOF everysec + RDB, `noeviction` 256mb.

## 외부 연동

| 대상 | 클라이언트 | 사용처 |
|---|---|---|
| KTO OpenAPI (KOR·PET·GALLERY·CNCTR·TARRLTE) | `app/core/kto_client.py` — 싱글턴, 재시도는 transient만(429·5xx·타임아웃) | 상세 lazy fetch · 채널 · 갤러리 임베딩 |
| Kakao Local (`coord2regioncode`) | `map/kakao_local.py` | `/map/region` 라벨 |
| Kakao·Google·Apple OIDC JWKS | `users/oidc.py`·`kakao_oidc.py` (fresh 1h / stale-on-error 24h) | 소셜 로그인 id_token 검증 |
| img.pictrip.org Worker | `app/core/kto_images.py` + `feed/services/display.py` (**발급 SSOT**) | Type1 한정 HMAC 서명 변환(`/t1/{width}/{sig}/…`, 폭 1620) — Type3·비KTO·secret 미설정은 원본 pass-through |
| Wikimedia Commons | pipeline이 URL 적재, backend는 표시만 | 해외 게시물 이미지 (저작자·라이선스·원본 링크 표기 의무) |

## 파이프라인 (CT111, 별도 Python 프로젝트)

backend와 **venv·코드 공유 없음** — 유일한 결합은 CT110의 `spots`·`sync_runs`.
CLI `pictrip-data`: `sync-daily`(04:00 KST 타이머) · `sync-full` ·
`validate-images`(주간) · `sync-overseas`(월간) · `backfill-overseas-thumbs` ·
`backfill-overseas-descriptions` · `load-codes`. KTO 재시도 정책은 backend와
동일(transient-only).
