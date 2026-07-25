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
| POST | `/agent/ask` | 여행 탭 질의 — 자유문·사진·조건 → 단계+답변+스팟 (아래) | — |
| GET | `/map/nearby` | 내 주변 (bbox+카테고리, ≤30) | — |
| GET | `/map/region` | 좌표→행정구역 라벨 (fail-open null) | — |
| GET | `/map/regions-tree` | 시도·시군구 트리 (centroid 포함, 24h 캐시) | — |
| GET | `/meta/version` | 버전·환경·ktoApiStatus | — |
| GET | `/health` *(루트, /v1 밖)* | liveness | — |

어드민 콘솔은 `/v1` 밖 `/admin` — 페이지 4종 + `/admin/api/*`(수집·임베딩
상태/트리거, 이력, 헬스, overseas 목록·`is_hidden` 토글). 서명 쿠키 세션,
`admin_users` 인증. `images` 모듈은 공개 엔드포인트 0(임베딩 잡 전용).

## `POST /agent/ask`

여행 탭의 유일한 질의 표면. 자유문·사진·정형 조건을 한 요청으로 받아 한 번에
응답한다(스트리밍 없음 — [ADR 0009](../adr/0009-travel-tab-conversational-agent.md)).
사진이 붙으면 `multipart/form-data`, 아니면 JSON. rate-limit 20/분/IP.

**요청**

| 필드 | 타입 | 비고 |
|---|---|---|
| `question` | string | 사진이 없으면 필수. 사진에 덧붙이면 지역·근처 조건으로 함께 적용된다 |
| `photo` | file | multipart 전용. 임베딩 후 즉시 폐기, **디스크에 닿지 않는다**(아래) |
| `region` | `all`\|`capital`\|`gangwon`\|`chungcheong`\|`jeolla`\|`gyeongsang`\|`jeju` | 기본 `all` |
| `when` | `any`\|`today`\|`weekend`\|`next_week` | 기본 `any` |
| `who` | `any`\|`solo`\|`duo`\|`kids`\|`pets` | 기본 `any` |
| `lat` / `lng` | float | 거리 정렬·`내 근처` 의도에만 사용 |

정형 조건 3종은 LLM을 거치지 않는다. Gemini Flash는 `question` → 구조화 의도
(카테고리 키워드 · 지역 힌트 · 지목된 장소 · 혼잡도 선호 · 실내 여부 · 근처 여부)
추출에만 쓴다. 의도에 `outOfScope`가 서면("파리 가볼 만한 곳") 검색을 돌리지 않고
`AGENT_OUT_OF_SCOPE`로 끊는다 — 빈 의도로 전국 검색이 돌아 엉뚱한 국내 스팟을
추천하는 일이 없도록. 단 사진 질의는 예외로, 해외 사진 → 국내 매칭이 제품의 본래
동작이라 그대로 진행한다. 세 조건이 실제로 하는 일은 다르다:

| 조건 | 효과 |
|---|---|
| `region` | `spots.addr1` 접두사 하드 필터 (`capital` = 서울·경기·인천 …). **질문에 지역이 나오면 그쪽이 이긴다** — `제주 계곡`이면 시트가 `전국`이어도 제주로 좁힌다 (`regions` 테이블로 시도 매핑) |
| `who` | 카테고리 키워드를 보탠다 (`kids` → 테마파크·동물원·체험, `pets` → 공원·산책로) |
| `when` | **필터하지 않는다** — `spot_concentration`은 일일 스냅숏이라 미래 예측이 없다. 답변 문구에만 실린다 |

**응답 `data`**

| 필드 | 타입 | 비고 |
|---|---|---|
| `steps[]` | `{tool, label, badge}` | 서버가 **실제로 실행한** 툴 순서. `badge`는 그 단계 후 잔여 건수(`128곳`) 또는 근거 표시(`Gemini` · `pgvector`) |
| `answer[]` | `{text, emphasis}` | 문장 조각. `emphasis=true`는 `accentText` 800으로 렌더 (HTML을 보내지 않는다) |
| `spots[]` | `{contentId, title, regionLabel, imageUrl, tag, lat, lng}` | 상위 4곳. `tag`는 카드 좌상단 배지(`하위 8%` · `4.2km` · `유사도 86%`) |
| `totalCount` | int | `전체 N곳 보기`의 N |
| `suggestions[]` | string | 후속 제안 칩 3개 |

`imageUrl`은 서명된 `img.pictrip.org` 프록시 URL — 클라이언트는 변형 없이 그대로
쓴다(`cpyrhtDivCd=Type3` 무변형, [ADR 0005](../adr/0005-kto-image-policy.md)).

**툴** — `steps[].tool` 값이자 서버가 고정 순서로 실행하는 단위.

| tool | 구현 | 하는 일 |
|---|---|---|
| `intent` | `agent/services/intent.py` | Gemini Flash 자유문 → 구조화 의도 |
| `photo_match` | `agent/services/photo.py` | CLIP 임베딩 → pgvector 유사도 (지역 조건은 SQL에 포함) |
| `resolve_place` | `agent/services/resolve.py` | 장소명 → KTO 스팟 (질문이 특정 장소를 지목할 때) |
| `category_search` | `agent/repositories.py` + `lcls_systm_codes` | 카테고리 키워드 → lcls 코드 → 스팟 조회 |
| `title_search` | `spots/services/search.py` | 키워드가 lcls 코드에 하나도 안 걸릴 때의 폴백 (스팟 이름 trigram, 지역별로 각각 조회) |
| `concentration` | `agent/services/retrieve.py` | 집중률 백분위 하위/상위 30%로 추림. 후보가 적어 아무도 30% 안에 못 들면 가장 한적한/붐비는 쪽 4곳을 남긴다 (선호를 버리고 전체로 되돌리지 않는다) |
| `nearby` | `agent/repositories.py` | 현재 위치 기준 거리순 (SQL `ORDER BY`) |

**업로드 사진은 디스크에 닿지 않는다.** Starlette의 multipart 파서는 파일 파트를
`SpooledTemporaryFile(max_size=1MB)`에 담아 1MB를 넘으면 임시 파일로 롤오버한다 —
일반적인 폰 사진이 전부 여기 걸린다. 그래서 (1) 본문을 `MAX_BODY_BYTES`(8MB +
64KB) 상한으로 **스트리밍하며** 버퍼링해 초과분은 파싱 전에 `IMAGE_INVALID`로
끊고, (2) `MultiPartParser.spool_max_size`를 그 상한까지 올려 허용 범위는
메모리에만 머물게 한다. 롤오버가 일어나면 실패하는 회귀 테스트가 있다
(`test_photo_upload_never_rolls_over_to_disk`).

**장소명만 물으면 그 장소만 돌려준다.** 질문이 특정 장소만 지목하고 카테고리·지역
키워드도 근처·혼잡도 선호도 없으면 broad search를 아예 건너뛴다. 해석에 실패하면
`AGENT_NO_RESULTS` — 물어본 장소와 무관한 전국 스팟을 붙이지 않는다.

**키워드가 코드에 안 걸리면 넓히지 않고 좁힌다.** LLM이 뽑은 카테고리 키워드가
`lcls` 코드로 하나도 매핑되지 않으면 조건 없는 전국 검색이 아니라 `title_search`
폴백으로 가고, 그것도 비면 `AGENT_NO_RESULTS`다. 유형을 물었는데 아무 관광지나
추천하지 않는다.

**사진 질의도 덧붙인 말을 읽는다.** 사진 + 텍스트면 CLIP 임베딩과 Gemini 의도
추출을 **동시에** 돌리고(지연은 둘 중 큰 쪽), 그 다음 지역 조건을 **벡터 SQL 안에**
넣어 검색한다 — 전역 상위 12개를 뽑고 나서 지역으로 거르면 13위 밖의 그 지역
후보를 아예 못 본다. 의도 추출이 실패해도 사진 결과는 그대로 내려간다(best-effort).

**정렬도 필터도 LIMIT보다 먼저다.** 후보 400개를 임의 순서로 자른 뒤 파이썬에서
정렬하거나 거르면 진짜 가까운/한적한/그 지역의 곳이 잘려나간다. 거리·집중률 정렬은 `ORDER BY`로 내려가고
`LIMIT`은 그 뒤에 붙는다. 혼잡도 백분위도 `cume_dist()` 윈도로 **필터를 만족하는
전체 집합** 기준으로 계산한다 — 잘린 400개 안의 상대 순위가 아니다.

카드 태그 우선순위는 거리(`4.2km`) → 혼잡도 백분위(`하위 8%`) → 혼잡 라벨
(`붐빔`·`보통`·`한산`), 사진 질의는 `유사도 86%`.

## 에러 코드

정본 `app/web/errors.py` — union은 `mobile/src/lib/app-error.ts`와 동기.
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
| `AGENT_INTENT_UNAVAILABLE` | 502 | Gemini Flash 무응답 → 재시도 칩 |
| `AGENT_NO_RESULTS` | 422 | 조건에 맞는 곳 0 → 조건 완화 안내 |
| `AGENT_OUT_OF_SCOPE` | 422 | 해외 여행지 질의 → 국내만 가능 안내 |
| `INTERNAL_ERROR` | 500 | 미분류 기본값 |

---
관련: [architecture](../explanation/architecture.md) · [database-schema](database-schema.md) · [glossary](../explanation/glossary.md)
