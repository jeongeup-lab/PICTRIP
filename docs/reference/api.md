# API 레퍼런스

> 공개 API(`/v1`)와 에러 코드의 조회용 표. 라우트 정본은
> `backend/app/modules/*/routes.py`, 자동 문서는 `/v1/docs`.

모든 응답은 JSend `{data, error, meta}`. 인증 열이 비면 게스트 가능.

## 엔드포인트

| Method | Path | 목적 | 인증 |
|---|---|---|---|
| POST | `/auth/oauth/{provider}` | OIDC id_token → 토큰쌍 (kakao·google·apple) | — |
| POST | `/auth/email/signup` | 이메일 가입 (rate-limit 5/분/IP) | — |
| POST | `/auth/email/login` | 이메일 로그인 (rate-limit 10/분/IP) | — |
| POST | `/auth/refresh` | 슬라이딩 재발급 (denylist 확인) | refresh 본문 |
| POST | `/auth/logout` | 멱등 로그아웃 (jti denylist) | — |
| GET | `/users/me` | 내 프로필 | JWT |
| DELETE | `/users/me` | 탈퇴 (익명화·OAuth 해제·토큰 폐기) | JWT |
| GET / PUT | `/users/me/consents` | 동의 상태 조회/upsert | JWT |
| GET | `/users/me/saved` | 저장 목록 (커서) | JWT |
| POST / DELETE | `/users/me/saved/{contentId}` | 저장/해제 (멱등) | JWT |
| GET | `/spots/{contentId}` | 스팟 상세 (KTO lazy fetch, 7일 캐시) | — |
| GET | `/feed` | 홈 피드 — 해외 게시물 (seed+cursor, 6개) | — |
| GET | `/explore` | 탐색 그리드 (동일 소스, 30개) | — |
| GET | `/overseas/{id}/matches` | 해외→국내 매칭 3곳 | — |
| GET | `/home/channels` | 채널 메타 (가용성 포함) | — |
| GET | `/home/channels/{key}` | 채널 카드 (`around`는 lat/lng 필요) | — |
| GET | `/map/nearby` | 내 주변 (bbox+카테고리, ≤30) | — |
| GET | `/map/region` | 좌표→행정구역 라벨 (fail-open null) | — |
| GET | `/map/regions-tree` | 시도·시군구 트리 (centroid 포함, 24h 캐시) | — |
| GET | `/meta/version` | 버전·환경·ktoApiStatus | — |
| GET | `/health` *(루트, /v1 밖)* | liveness | — |

어드민 콘솔은 `/v1` 밖 `/admin` — 페이지 4종 + `/admin/api/*`(수집·임베딩
상태/트리거, 이력, 헬스, overseas 목록·`is_hidden` 토글). 서명 쿠키 세션,
`admin_users` 인증. `images` 모듈은 공개 엔드포인트 0(임베딩 잡 전용).

## 에러 코드

정본 `app/core/exceptions.py` — union은 `mobile/src/lib/app-error.ts`와 동기.
**새 코드는 양쪽을 함께 갱신한다.**

| code | HTTP | 용도 |
|---|---|---|
| `VALIDATION_FAILED` | 422 | 요청 형식 부적합 |
| `AUTH_TOKEN_INVALID` / `AUTH_TOKEN_EXPIRED` | 401 | 무효/만료 (만료는 모바일 silent refresh 트리거) |
| `GUEST_FORBIDDEN` | 403 | 게스트 불가 → 로그인 시트 |
| `PERMISSION_DENIED` | 403 | 권한 없음 |
| `RESOURCE_NOT_FOUND` | 404 | 리소스 없음 |
| `DUPLICATE_RESOURCE` | 409 | 중복 |
| `EMAIL_TAKEN` | 409 | 가입된 이메일 |
| `AUTH_INVALID_CREDENTIALS` | 401 | 이메일/비번 불일치 |
| `AUTH_SESSION_REVOKED` | 401 | 폐기된 세션 — 재로그인 |
| `IMAGE_INVALID` | 422 | 미지원 이미지 |
| `RATE_LIMITED` | 429 | 요청 과다 |
| `LBS_CONSENT_REQUIRED` | 403 | 위치 동의 필요 |
| `KTO_API_UNAVAILABLE` | 502 | KTO 무응답 → 부분 degrade |
| `OAUTH_PROVIDER_UNAVAILABLE` / `OAUTH_ID_TOKEN_INVALID` | 502 / 401 | 소셜 공급자 장애 / id_token 무효 |
| `SESSION_STORE_UNAVAILABLE` | 503 | 세션 저장소 일시 장애 |
| `ADMIN_UNAUTHORIZED` · `ADMIN_HISTORY_NOT_FOUND` · `ADMIN_TRIGGER_FAILED` · `ADMIN_VALIDATION` | 401·404·502·422 | 어드민 전용 |
| `INTERNAL_ERROR` | 500 | 미분류 기본값 |

---
관련: [architecture](../explanation/architecture.md) · [database-schema](database-schema.md) · [glossary](../explanation/glossary.md)
