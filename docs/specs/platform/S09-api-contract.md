# S9 — API 계약 (화면 → 엔드포인트)

> 세션 S9. 입력 SSOT: `session-context.md`(잠긴 결정·교차 reconcile), 화면 스펙
> S1·S2·S3·S4·S5·S6, DB 설계 S7, 루트 `CLAUDE.md`(Conventions·Prohibitions).
> **현 백엔드 코드가 ground truth** — 이 문서는 화면들이 넘긴 data needs를 JSend 계약으로
> 형식화하고, 현 코드와의 차이를 reconcile 메모로 남긴다(구현은 S10).
> 캐시·딥링크·호스팅 = S8, 마이그레이션 적용순서·모듈코드 제거 = S10.

이 세션에서 crosscheck로 확정한 사실(코드 권위):
- API 베이스 프리픽스 `API_V1_PREFIX = "/v1"`. 모든 도메인 라우터가 `/v1` 하위.
- 엔벨로프·`ok()`/`err()`·`AppError` 코드는 §1·§2에 실측 인용.
- `/health`는 루트(`include_in_schema=False`, ALB liveness) — 프롬프트의 `/system/health`는 이 루트 `/health`로 문서화.
- `user_consents` 컬럼: `location_consent bool`·`photo_consent bool`·`notification_consent bool`(S7 드롭)·`terms_version varchar(16) NOT NULL`·`consented_at`. consent는 **boolean**.

---

## 이 세션에서 확정한 결정 (5)

| # | 결정 | 근거 |
|---|---|---|
| E1 | **화면이 소비하지 않는 엔드포인트 전부 제거** — `/spots/{id}/similar`·`/spots/{id}/related`·`/moods`·`/moods/{code}/spots`·`/spots/batch` | honest-minimal(죽은 엔드포인트 금지). 사진검색=`/taste/photo-search`, 상세 주변=`/map/nearby`, 홈 무드=`/home/feed`가 대체; batch는 홈/큐레이션/상세가 스팟을 인라인으로 내려줘 소비처 없음 |
| E2 | **`/legal`은 API 아님** — 앱 상수 4개 `{slug,title}` + `https://pictrip.org/legal/{slug}` 인앱 WebView | S6 D1(백엔드 테이블/번들 둘 다 안 씀). 본문 호스팅 = **Cloudflare Pages 정적**(S8 §3 확정; Notion 기각) |
| E3 | **`/users/me/saved` = 커서 + limit 결합** | 그리드(13) 무한스크롤=커서, 레일(14) 최근 10개=limit. 엔벨로프 `meta.pagination{nextCursor,hasMore,count}` 활용 |
| E4 | **평면 `/regions`(17 시도 flat) 제거** | region picker(12)는 `/map/regions-tree`(nested+centroid)를 씀 → 평면 버전은 소비처 없는 고아 |
| E5 | **`GET /users/me` 직렬화 = `displayName`/`avatarUrl`** | S6 신원 표면. 현 `name`/`profileImageUrl` → 직렬화 리네임은 S10(DB 컬럼 `profile_image_url`은 유지) |

---

## 1. 공통 규약

### 1.1 JSend 엔벨로프 (`app/core/schemas.py`)

모든 응답은 `{ data, error, meta }`. 성공=`ok()`, 실패=`err()`.

```
Envelope        { data: T|null, error: ErrorPayload|null, meta: ResponseMeta }
ErrorPayload    { code: str, message: str, details: ErrorDetail[], traceId: str|null }
ResponseMeta    { traceId: str|null, requestedAt: datetime, pagination: PaginationMeta|null }
PaginationMeta  { nextCursor: str|null, hasMore: bool, count: int }
```

- `traceId`는 `TraceIdMiddleware`가 `X-Trace-Id` 헤더 또는 `uuid4().hex[:16]`로 주입,
  `meta.traceId`(+오류 시 `error.traceId`)에 자동 채움. 응답 헤더 `X-Trace-Id`도 세팅.
- 클라이언트는 **`err.code`로만 분기**(메시지 문자열 분기 금지, `CLAUDE.md`). `traceId`는 콘솔/로그용.
- 페이지네이션을 쓰는 엔드포인트만 `meta.pagination`을 채움(나머지는 null).

### 1.2 인증

- 보호 엔드포인트: `Authorization: Bearer <accessToken>`. access=메모리, refresh=secure-store(`CLAUDE.md`).
- 게스트: 헤더 없음. 게스트 OK 엔드포인트는 헤더 무관 동작(홈·상세·검색·지도).
- 토큰 누락/위조 → `AUTH_TOKEN_INVALID(401)`, 만료 → `AUTH_TOKEN_EXPIRED(401)`,
  jti 덴리스트 → `AUTH_SESSION_REVOKED(401)`. 모바일은 401 시 1회 `/auth/refresh` → 실패면 게스트 강등.
- 인증 모델(S8 §2.2 확정): sessions/devices 폐기, **refresh 회전 없음**(denylist 단일 모델), 로그아웃·탈퇴는 Redis **jti 덴리스트**(`denyjti:{jti}`). 발급 시 Redis 쓰기 0, refresh는 JWT(sig+exp) 검증 + `EXISTS denyjti:{jti}`만. 근거: 회전 모델은 단일 홈서버서 fail-closed(Redis 소실=전원 강제 로그아웃)·과설계.

### 1.3 canonical 스팟 카드 (레이어링)

교차결정 C1 — 모든 스팟 리스트가 공유하는 **코어 카드**(camelCase + KTO명):

```
SpotCard (코어)  { contentId, title, firstImageUrl: str|null, category: str|null }
```

- `category` = `lcls_systm_codes.lcls_systm3_nm`(**세분 subtype 라벨**, 조인 `spots.lcls_systm3 → lcls_systm3_cd`).
  `lcls_systm3` null이면 `category=null`(카드 라벨 생략, S7 §10). **칩 필터의 coarse 버킷(§5.MAP)과는 별개.**
- `firstImageUrl` null이면 클라가 inset-gray 폴백(이미지 바이트 저장 금지, URL만).
- 엔드포인트별 **확장 필드**(코어에 더함):
  | 확장 필드 | 추가하는 엔드포인트 | 의미 |
  |---|---|---|
  | `similarity: float`(0~1) | `/taste/photo-search` | 코사인 유사도(클라 ×100 반올림) |
  | `distance: float`(m) | `/taste/photo-search`(위치 시) | 쿼리 지점 거리 |
  | `dist: float`(m) | `/map/nearby` | 중심점 거리(거리순 정렬 기준) |
  | `regionName`,`sigunguName: str\|null` | `/taste/photo-search`·`/spots/{id}`·`/map/nearby` | "유형 · 지역" 메타 |
  | `addr1`,`mapx`,`mapy` | `/spots/{id}`·`/map/nearby` | 주소·좌표 |
  | `overview: str\|null` | `/map/nearby` | KTO overview 첫 줄(verbatim, null이면 생략) |
  | `congestion: "low"\|"medium"\|"high"\|null` | `/home/feed`·`/curations/{slug}`·`/spots/{id}`·`/map/nearby`·`/taste/photo-search` | 혼잡도(붐빔도) 텍스트 칩. 데이터 있으면 채움, 없으면 `null`(클라 배지 숨김) |

  **`congestion` — 혼잡도 필드 (이 파일이 권위, S11 §7-A D1):** canonical 카드를 내리는 모든 엔드포인트가
  데이터 있으면 채우는 **선택 확장 필드**. 다른 스펙은 이 정의를 참조한다.
  - **출처**: `spot_concentration` 테이블(KTO 15128555 "한국관광공사 관광지별 방문자 집중률 예측" — 향후 30일
    **상대 집중률 0~100**, 100=가장 붐빔)을 `content_id`로 JOIN. **오늘/현재 윈도우 값** `v`를 버킷팅.
  - **버킷**: `v < 34` → `"low"`(한산) · `34 ≤ v ≤ 66` → `"medium"`(보통) · `v > 66` → `"high"`(붐빔).
  - **null 규칙**: 해당 스팟의 집중률 데이터가 없으면(JOIN 미스/윈도우 공백) `congestion=null`.
    클라는 null이면 칩을 숨긴다(honest-minimal — 가짜 값/플레이스홀더 금지).
  - 트렌딩 **엔드포인트**(`/spots/trending`)는 계속 제거하되(§8.1·§10) **`spot_concentration` 데이터(테이블)는
    이 필드의 소스로 보존**한다. 무채색 UI라 색 배지가 아닌 텍스트 칩으로만 노출.

> 코어는 **최소**로 유지(홈 카드는 region 메타를 안 씀). 현 백엔드 `SpotCard`는 이미
> `{contentId,title,firstImageUrl,addr1,mapx,mapy,category}`라 코어+일부 확장을 한 클래스에 둠 —
> 직렬화 시 화면이 안 쓰는 필드(addr1/mapx/mapy)는 카드 컨텍스트에서 무시 가능(과한 분리 비용 회피).

### 1.4 공유 유틸 / 표기 (클라이언트)

- **거리**: `formatDistance(m)` 단일 함수(C2) — `<1km → {정수}m` / `1–10km → 소수1 km` / `≥10km → 정수 km`.
  서버는 항상 미터(`dist`/`distance`)를 내림. 사진검색(S4)·지도(S5) 동일.
- **유사도**: 서버는 원시 코사인 `similarity`(0~1)를 내림. **표시는 원시 `round(similarity × 100)%`를 쓰지 않는다**
  (정정 — S11 §2/§4 D3). 코사인 절대값은 사용자에게 직관적이지 않고 분포가 좁아 % 노출이 오해를 부른다 →
  클라가 **버킷 라벨**(예 "매우 비슷함/비슷함/관련 있음") 또는 결과 집합 기준 **스트레치(min-max 정규화)**로 변환해
  표시. 정렬·임계 판단은 원시 `similarity`로 유지.

---

## 2. AppError 코드 전체 (`app/core/exceptions.py`)

신규 코드 없음 — 전부 기존 재사용. 계약상 자주 쓰는 것 굵게.

| code | HTTP | 의미 |
|---|---|---|
| `INTERNAL_ERROR` | 500 | 미분류 서버 오류 |
| **`VALIDATION_FAILED`** | 422 | 요청 형식/파라미터 오류 |
| **`AUTH_TOKEN_INVALID`** | 401 | 토큰 누락/위조 |
| **`AUTH_TOKEN_EXPIRED`** | 401 | access 만료 |
| **`AUTH_SESSION_REVOKED`** | 401 | jti 덴리스트(로그아웃/탈퇴 후) |
| `GUEST_FORBIDDEN` | 403 | 게스트 불가 기능 |
| `PERMISSION_DENIED` | 403 | 권한 없음 |
| **`RESOURCE_NOT_FOUND`** | 404 | 스팟/큐레이션 없음 |
| `DUPLICATE_RESOURCE` | 409 | 중복 |
| **`IMAGE_INVALID`** | 422 | 이미지 형식/크기 |
| `RATE_LIMITED` | 429 | 과다 요청 |
| `KTO_API_UNAVAILABLE` | 502 | KTO API 무응답 |
| `LBS_CONSENT_REQUIRED` | 403 | 위치 동의 필요 |
| **`OAUTH_PROVIDER_UNAVAILABLE`** | 502 | 소셜 제공자 무응답 |
| **`OAUTH_ID_TOKEN_INVALID`** | 401 | id_token 검증 실패 |
| `LLM_API_UNAVAILABLE` | 502 | (이 릴리스 미사용 경로) |
| `SESSION_STORE_UNAVAILABLE` | 503 | Redis 일시 장애 |
| `MAX_5_MOODS` | 422 | (무드 기능 제거로 미사용) |

> `Max5Moods`·`LlmApiUnavailable`는 제거 기능(무드 선택·코스 LLM)에 묶여 사실상 사장 — 코드 정의는
> 남기되 이 계약의 어떤 엔드포인트도 발생시키지 않음.

---

## 3. users 모듈 — 인증 · 계정

### 3.1 `POST /v1/auth/oauth/{provider}`  ·  게스트
- `provider` ∈ `kakao` | `google` | `apple` (경로 파라미터). **현 코드는 `/auth/oauth/kakao` 리터럴** → `{provider}` 일반화는 S10(google/apple 구현 동반).
- 요청 `{ idToken: str, nonce?: str }`. (3종 OIDC `id_token` 통일 — S1 잠금. 카카오 기존 access_token+`/v2/user/me` 폐기.)
- 응답 200 `{ accessToken, refreshToken, expiresIn, user }`, `user = UserPublic`(§3.4 형).
- 흐름: id_token 검증 → `user_auth_providers(provider, provider_user_id) UNIQUE` upsert → 자체 JWT(access+refresh) 발급.
- **id_token 검증 규약(공급자별 — S11 §3 D4):** 모든 클레임을 **전수 검증**한다.
  공통: 공급자 **JWKS로 서명 검증**(kid 매칭) · `iss`·`aud`·`exp`(만료) 확인 · **`alg:none` 거부**(허용 alg 화이트리스트) ·
  `nonce` 제공 시 요청 nonce와 일치. **유저 식별 키 = `provider + sub`**(이메일은 식별자로 쓰지 않음 — 변경 가능/재할당).
  - **Apple**: `iss = https://appleid.apple.com` · `aud = 네이티브 앱 bundle ID` · alg `ES256` ·
    `nonce = SHA-256(raw nonce)`를 **base64url(패딩 없음)**으로 비교.
  - **Google**: `iss = accounts.google.com`(또는 `https://accounts.google.com`) ·
    `aud ∈ 플랫폼별 client_id 집합`(iOS/Android/web 각 client_id 허용).
  - **Kakao**: **OIDC 활성 + `scope=openid`** 전제 · `iss = https://kauth.kakao.com` · `aud = 카카오 앱 키` ·
    JWKS 서명. (기존 access_token + `/v2/user/me` 방식은 폐기 — id_token 통일, S1.)
- 에러: `OAUTH_ID_TOKEN_INVALID(401)`(서명/iss/aud/exp/nonce/alg 위반) · `OAUTH_PROVIDER_UNAVAILABLE(502)` · `VALIDATION_FAILED(422)`.
- 애플 첫 로그인만 이름 제공, 재로그인 시 이름 null 정상(닉네임 = 공급사 default/익명).

### 3.2 `POST /v1/auth/refresh`  ·  게스트
- 요청 `{ refreshToken }`. 응답 200 `{accessToken, refreshToken, expiresIn, user}` — **회전 없음 + 슬라이딩 만료**(정정 — S11 §3 D4): 입력 refresh를 **그대로 에코하지 않는다**. 새 access를 발급하면서 refresh JWT도 **새 `exp = now + 30d`로 재민트**(슬라이딩 — 활성 사용자는 재로그인 없이 세션 유지). 이때 **`jti`·기타 claims는 동일하게 유지**(회전 아님 — 토큰 패밀리/도난 탐지/이전 토큰 무효화 없음). 클라는 응답의 refreshToken으로 secure-store를 갱신. (이전 "입력 refreshToken 그대로 에코" 결정은 폐기.)
- 검증: refresh JWT(sig+exp) + `EXISTS denyjti:{jti}`. denylist 조회는 **fail-open**(Redis 일시장애 시 통과 — 회전 모델의 fail-closed 회피, S8). 에러 `AUTH_TOKEN_INVALID/EXPIRED(401)` · `AUTH_SESSION_REVOKED(401)`(덴리스트 적중).
- 스플래시(01) silent refresh가 사용 — 실패는 화면 에러 아님(조용한 게스트 강등, S1).

### 3.3 `POST /v1/auth/logout`  ·  게스트(토큰 보유)
- 요청 `{ refreshToken?: str }`. 응답 200 `{}` (**멱등** — 이미 폐기돼도 200).
- refresh의 `jti`를 Redis 덴리스트에 추가. 마이(14) 로그아웃(D5).

### 3.4 `GET /v1/users/me`  ·  **인증**
- 응답 200 `UserPublic = { id, displayName: str|null, email: str|null, avatarUrl: str|null, isOnboarded: bool, createdAt: datetime|null }`.
- **직렬화 리네임(E5)**: 현 `name → displayName`, `profileImageUrl → avatarUrl`. DB 컬럼 `users.profile_image_url`은 유지(S7). 폴백(모노그램/'여행자'/공급사 라벨)은 클라(S6).
- **아바타 폴백(S11 §6 D7)**: `avatarUrl`이 null이거나 로드 실패(공급사 이미지 URL이 **404/만료**)면 클라가 **모노그램 폴백**(displayName 첫 글자, displayName도 null이면 '여행자')으로 렌더. 서버는 이미지 바이트를 저장하지 않으므로(URL만, KTO/프로필 동일 원칙) URL 유효성을 보장하지 않음 → 깨진 이미지가 아니라 모노그램으로 떨어진다.
- **consents 버전(S11 §6 D7)**: `UserPublic`에는 약관 버전이 없음. `user_consents.terms_version`은 **최초 로그인 시점의 terms_version**으로 기록되며(이력 테이블 없음 — §3.6) 이후 동의 갱신은 `PUT /users/me/consents`로 덮어쓴다.
- 에러 `AUTH_*`.

### 3.5 `DELETE /v1/users/me`  ·  **인증**
- 응답 204. cascade 삭제: `users` + `user_saved_spots` + `user_consents` + `user_auth_providers` + 토큰 jti 덴리스트(S6 D6).
- 이중 확인 Alert는 클라(S6). 에러 `AUTH_*`.

### 3.6 `PUT /v1/users/me/consents`  ·  **인증** (신규)
- 로그인 직후 OS 권한 **스냅샷 upsert** + 포그라운드 재동기화(S1 §consent).
- 요청 `{ locationConsent: bool, photoConsent?: bool, termsVersion: str }`.
  - `locationConsent` = OS 위치 권한 `granted`→true / `denied`·`undetermined`→false.
  - `termsVersion` 필수(컬럼 NOT NULL, 예 `"v1.0"`) — 동의 버전 추적(별도 이력 테이블 없음, lean).
  - `photoConsent` 선택(미전송 시 기존값 유지/기본 false).
- 동작: `user_consents`(PK=user_id) upsert + `consented_at=now()`.
- 응답 200 `{ locationConsent, photoConsent, termsVersion, consentedAt }`. 에러 `AUTH_*` · `VALIDATION_FAILED`.
- 게스트는 호출 안 함(서버 consent 레코드 없음, OS 권한만 — S1).

### 3.7 `GET /v1/users/me/saved?cursor=&limit=`  ·  **인증** (E3)
- 쿼리 `cursor?`(불투명) · `limit`(기본 24, 1–60). 레일(14)=`limit=10`, 그리드(13)=커서 무한스크롤.
- 응답 200 `data = [ SpotCard(코어) ]`, `meta.pagination = { nextCursor, hasMore, count }`.
  - `nextCursor` = `base64(created_at, content_id)` 불투명 토큰. 마지막 페이지면 null·`hasMore=false`.
- 정렬: 스크랩 최근순(`user_saved_spots.created_at DESC`).
- *reconcile: 현재 `limit`만(기본 100/최대 200) · 응답 `list[SpotCard]` 플랫 · 커서 없음 → 커서+pagination meta 도입은 S10.*
- 에러 `AUTH_*`.

### 3.8 `POST /v1/users/me/saved/{contentId}`  ·  **인증**
- 응답 201(신규)·200(이미 저장) `{ saved: true }`(SavedSpotToggle). 멱등 친화.
- 스크랩 추가 / 그리드 실행취소(D2) / 게스트 로그인 후 수동 재탭(D3·S3 §4.7).
- 에러 `AUTH_*` · 미존재 contentId → `RESOURCE_NOT_FOUND(404)`.

### 3.9 `DELETE /v1/users/me/saved/{contentId}`  ·  **인증**
- 응답 204 (**멱등**). 낙관적 해제(D2) — 실패 시 클라 롤백 + 토스트.
- 에러 `AUTH_*`.

---

## 4. taste 모듈 — 사진 검색

### 4.1 `POST /v1/taste/photo-search`  ·  게스트
- 요청: **multipart** `image`(필수, 단일) + 쿼리 `lat?` · `lng?`(위치 권한 **이미 허용** 시에만 첨부 — 흐름 중 팝업 금지, S4).
- 응답 200:
  ```
  {
    matches: [ SpotCard(코어) + {
      similarity: float,        // 0~1 (원시 코사인; 표시는 클라 버킷/스트레치 — §1.4)
      distance?: float,         // m, lat/lng 줬을 때만
      regionName?: str|null,
      sigunguName?: str|null,
      congestion?: "low"|"medium"|"high"|null   // 혼잡도(§1.3), 데이터 있을 때만
    } ],
    queryHadLocation: bool      // 거리/정렬칩 노출 판단(10)
  }
  ```
- 서버 규칙(정정 — S11 §2/§4 D3): 임계는 **고정 0.60이 아니라 캘리브레이션 값**을 쓴다.
  라벨링 표본에서 **FP/FN 교차점**으로 결정(예상 범위 0.50~0.70)하고, 임계 통과가 적을 때 결과가 비지 않도록
  **top-N 소프트 플로어**(임계 미달이라도 상위 N개는 내림)를 둔다. **최대 ~30개**, 유사도 내림차순.
  소프트 플로어로도 0건이면 **정상 빈 200**(에러 아님 → 10 empty 상태). 정렬(유사도↔거리)은 **클라 재정렬**.
- **KTO 불변 규칙(C2/S4)**: 업로드 바이트는 메모리 추론 후 **즉시 폐기**(DB/디스크/로그/외부전송 금지). 응답에 원본 이미지 URL 없음(결과 히어로=클라 로컬 이미지).
- 에러: `IMAGE_INVALID(422)` · `VALIDATION_FAILED(422)` · `RATE_LIMITED(429)`. (네트워크/5xx는 09에서 인라인 처리.)
- *reconcile: 현재 `list[SimilarNeighbor]`(쿼리 `limit`, `distance`만, similarity·lat/lng·queryHadLocation·region 메타 없음, 객체 래핑 없음) → 위 형으로 재구성은 S10. 임계는 캘리브레이션+소프트 플로어로(고정 0.60 폐기, S11 §4 D3). `PhotoSearchResult{sessionId,detectedMoods,topSpots}`(무드 검출형)는 폐기.*

---

## 5. spots 모듈 — 홈 · 큐레이션 · 상세 · 배치

### 5.1 `GET /v1/home/feed`  ·  게스트 (신규)
- 응답 200 `{ heroes: [정확히 6], rails: [정확히 3] }` (개수 불변, 서버가 슬롯 큐레이션 교체 — S2).
  ```
  heroes[i] = { id, slug, title, subtitle, coverUrl }     // 스팟 목록 없음(가벼움). title은 \n verbatim(pre-line)
  rails[j]  = { id, title, subtitle, spots: [≤8 SpotCard(코어) + congestion?] }
  ```
- 레일 카드는 코어 SpotCard에 데이터 있으면 **`congestion`**(§1.3)을 채움(없으면 null). 히어로는 스팟 카드가 아니라 미적용.
- `coverUrl` = `cover_spot_id`의 `firstImageUrl`(없으면 `curation_spots[0]` 폴백, S2). 손픽 없으면 테마-일치 랜덤(결정적 seed·일 캐시 S8).
- 빈 카드/플레이스홀더로 채우지 않음(받은 만큼 ≤8 렌더). pull-to-refresh = 전체 재요청.
- 에러: 드묾(`INTERNAL_ERROR(500)`). 클라는 풀화면 재시도(S2).

### 5.2 `GET /v1/curations/{slug}`  ·  게스트 (신규)
- 경로 = **slug**(안정 식별·딥링크 키, `curations.slug` UNIQUE — S7). region 큐레이션 전용 상세(06).
- 응답 200 `{ id, type, slug, title, lead: str|null, intro: str|null, coverUrl, spots: [≤8 SpotCard(코어) + congestion?] }`.
  - `spots[]` 카드는 데이터 있으면 **`congestion`**(§1.3)을 채움(없으면 null).
  - **`subtitle` 생략**(목업 06 무 — B6/S2). `title`은 `\n` verbatim(pre-line).
- 에러: 미published/삭제 → `RESOURCE_NOT_FOUND(404)`("큐레이션을 찾을 수 없어요").

### 5.3 `GET /v1/spots/{contentId}`  ·  게스트
- 응답 200 `SpotDetailResponse` = SpotCard(코어) + :
  ```
  addr1, addr2?, mapx, mapy,
  overview: str|null,            // verbatim, 수정 금지
  homepage: str|null, tel: str|null,
  regionName: str|null, sigunguName: str|null,
  congestion: "low"|"medium"|"high"|null,   // 혼잡도(§1.3), 데이터 없으면 null
  detailStatus: "fresh"|"stale"|"unavailable",
  images: [ { originImageUrl, smallImageUrl? } ],
  intro: { usetime?, restdate?, parking?, infocenter?, firstmenu?, treatmenu? } | null
  ```
- **`moods[]` 제거**(본 화면 미사용 — S3 §7.4). `info_data` 미사용.
- 2계층 로딩(S3 §6): 기본 필드 즉시(카드 캐시 시드), 지연 enrich(`overview`/`images`/`intro`)는 7일 캐시. **KTO enrich 실패는 200 `detailStatus="unavailable"`**(부분 표시·소개만 인라인 재시도), 에러 아님.
- 에러: 미존재 → `RESOURCE_NOT_FOUND(404)`("존재하지 않는 장소"). 네트워크/캐시無 실패는 클라 전체화면 재시도.
- 메뉴(`firstmenu`/`treatmenu`)는 음식점에만 채워짐 → 클라는 존재 여부만 검사(S3 §4.3).

> region picker가 쓰던 **평면 `/regions`** 및 소비처 없는 **`/spots/batch`는 제거**(E1·E4) — §8 참조.

---

## 6. map 모듈 — 내 주변 · 지역

### 6.1 `GET /v1/map/nearby?lat&lng&radius&category`  ·  게스트
- 쿼리: `lat`·`lng`(필수) · `radius`(기본 **3000** m, S5 — *현 기본 1000 → reconcile*) · `category?`(coarse 버킷, 생략=전체).
- **coarse 버킷(NearbyCategory)** ↔ KTO 매핑(칩 필터, 카드 라벨과 별개 — B5):
  | 칩 | `category` 값 | KTO |
  |---|---|---|
  | 전체 | (생략) | 전체 |
  | 관광지 | `attraction` | contentTypeId 12 |
  | 음식점 | `food` | 39 |
  | 카페 | `cafe` | 39 + cat3 카페 |
  | 레저 | `leisure` | 28 |
  | 쇼핑 | `shopping` | 38 |
- 응답 200 `[ SpotCard(코어) + { addr1, mapx, mapy, dist, regionName?, sigunguName?, overview?, congestion? } ]`, 거리순, **상한 30**.
  - 카드 표시 라벨 `category`(코어) = **세분 `lcls_systm3_nm`**(칩의 coarse 버킷과 다름). 메타 `{지역}` = `sigunguName`/주소 파생.
  - **혼잡도 재도입(정정 — S11 §7-A D1)**: 이전 "`crowd` 필드 제거" 결정은 폐기하고 **`congestion`**(§1.3)으로 **재도입**한다(같은 의도, **텍스트 칩** — 색 배지 아님, 무채색 유지). 데이터 없으면 null(칩 숨김). 단 `crowd`라는 옛 필드명/색 배지는 부활시키지 않음. `firstImage2Url`은 계속 생략.
- 소비: 지도 리스트(11) · 스팟상세 주변레일(07, 자기 제외). 에러 `VALIDATION_FAILED(422)`(lat/lng 누락). empty = 정상 빈 배열(에러 아님).

### 6.2 `GET /v1/map/region?lat&lng`  ·  게스트 (유지)
- 응답 200 `{ sido?, sigungu?, dong?, label } | null`(Kakao `coord2regioncode`, Redis 캐시).
- 헤더 라벨(현위치/패닝검색 후) 생성용. **그대로 재사용**(S5 §3.2).

### 6.3 `GET /v1/map/regions-tree`  ·  게스트 (신규)
- 응답 200 `[ { regionCode, regionName, centroid: {lat,lng}, sigungus: [ { sigunguCode, sigunguName, centroid: {lat,lng} } ] } ]`.
- 17 시도 + 시군구(`{시도} 전체`=시도 centroid). 지역피커(12) 좌/우 리스트 + `검색` 재센터 좌표.
- **centroid = 런타임 AVG**(소속 스팟 `mapx/mapy` 평균, 빈 시군구=시도 폴백 — S7 §8). 정적이라 캐시(S8). 신규 컬럼/스크립트 없음.
- 에러: 드묾. 트리 fetch 실패 시 클라 시트 본문 재시도(S5 §2.4).

---

## 7. system / images 모듈

### 7.1 `GET /v1/meta/version`  ·  게스트
- 응답 200 `{ apiVersion, environment, ktoApiStatus }`. 마이(14) 앱버전은 **Expo Constants 로컬** — 이 엔드포인트는 메타 표시/디버그용(강제 업데이트 게이트 비목표, S1).

### 7.2 `GET /health`  ·  게스트 (루트, OpenAPI 제외)
- 응답 200 `{ status: "ok" }`. ALB/홈서버 liveness. 프롬프트의 `/system/health`=이 루트 `/health`(엔벨로프 미적용·`include_in_schema=False`).

### 7.3 images 모듈
- 이번 릴리스 **모바일 대면 엔드포인트 없음**. `GET /v1/admin/embeddings/status`(admin 스텁)만 존재 — 임베딩 운영용, 앱 계약 범위 밖.

---

## 8. 제거 / API 아님

### 8.1 제거 라우트 (현 코드 존재 → 삭제, 모듈코드 제거는 S10)
| 엔드포인트 | 사유 |
|---|---|
| `GET /v1/spots/search` | 텍스트 검색 비목표/retired(메모리 search_feature_retired) |
| `GET /v1/spots/trending` | 트렌딩 비목표(`spot_concentration` **테이블은 보존** — 이제 canonical 카드 `congestion`(§1.3)의 소스로 재활용; 엔드포인트만 제거 — S7·S11 §7-A D1) |
| `GET /v1/spots/by-region` | 큐레이션이 대체(비목표 — `session-context` 비목표) |
| `GET /v1/spots/{id}/similar` | 화면 미소비(E1). 사진검색=`/taste/photo-search` |
| `GET /v1/spots/{id}/related` | 화면 미소비(E1). 상세 주변=`/map/nearby` |
| `GET /v1/moods` · `GET /v1/moods/{code}/spots` | 홈 무드 레일=`/home/feed`(mood 큐레이션) 대체(E1). 무드 선택 기능 없음 |
| `GET /v1/spots/batch` | 소비처 없음(E1). 홈/큐레이션/상세가 스팟을 인라인으로 내려줌 |
| `GET /v1/regions`(평면 17) | region picker=`/map/regions-tree`가 대체(E4). 소비처 없음 |
| `GET /v1/recommendations/today-inspo` (+ **recommendations 모듈**) | today-inspo 비목표 |
| `POST /v1/courses/draft`·`/courses`·`GET/DELETE /courses/{id}` (+ **courses 모듈**) | 코스 일체 비목표 |
| `GET/PUT /v1/me/notifications` | 알림 비목표(`notifications` 테이블 드롭 — S7) |
| `POST /v1/analytics/events` | analytics 비목표(`analytics_events` 드롭 — S7) |

> 결과 백엔드 = **6 모듈**(users·taste·spots·images·map·system). courses·recommendations 모듈째 제거.

### 8.2 API 아님 (E2)
- **`/legal`** = 백엔드 엔드포인트 아님. 앱 상수 4개 `{ slug, title }`(`features/profile/constants`):
  `terms`(이용약관)·`privacy`(개인정보처리방침)·`location`(위치기반서비스)·`data-sources`(데이터 출처).
- 본문 = `https://pictrip.org/legal/{slug}` 인앱 WebView(KakaoWebMap이 이미 WebView 의존 → 신규 모듈 없음). 데이터 출처 페이지에 KTO 출처/이미지 저작권(`cpyrhtDivCd Type3`, URL 참조) 고지.
- 호스팅 = **Cloudflare Pages 정적**(apex `pictrip.org`, 무채색 HTML — S8 §3 확정). S6 D1 자체호스팅 안 유지, Notion 안은 기각.

---

## 9. 역추적표 (화면 → 엔드포인트)

| 화면(목업) | 엔드포인트 | 비고 |
|---|---|---|
| 01 스플래시 | `POST /auth/refresh` | refresh_token 있을 때만(silent), 실패=조용한 게스트 강등 |
| 02 온보딩 | — | 정적(서버 비의존) |
| 03 로그인 | `POST /auth/oauth/{provider}` | 성공 시 보류 액션 재개(퍼널 CTA 한정) |
| 04 권한 | — (로그인 유저는 `PUT /users/me/consents`) | 서버 호출 없음; 권한 스냅샷만 |
| 05 홈 | `GET /home/feed` | 히어로6+레일3, pull-refresh 재요청 |
| 06 큐레이션 상세 | `GET /curations/{slug}` | region 전용, 딥링크 slug |
| 07 스팟 상세 | `GET /spots/{contentId}` · `GET /map/nearby`(주변레일) · `POST/DELETE /users/me/saved/{contentId}` | 게스트 열람, 저장만 인증 |
| 08 사진 선택 | — | 입력 화면(분석 트리거만) |
| 09 분석 중 | `POST /taste/photo-search` | multipart image (+lat/lng), 09에서 대기/취소(abort) |
| 10 결과 | (09 응답 소비) → 카드탭 `GET /spots/{contentId}` | 클라 재정렬(유사도/거리) |
| 11 지도 | `GET /map/nearby` · `GET /map/region` | 점+반경, 패닝검색 라벨 |
| 12 지역 피커 | `GET /map/regions-tree` | 17 시도+시군구, centroid 재센터 |
| 13 저장 그리드 | `GET /users/me/saved?cursor=&limit=` · `DELETE`(해제) · `POST`(실행취소) | 무한스크롤(커서) |
| 14 마이 | `GET /users/me` · `GET /users/me/saved?limit=10` | 레일 최근 10 |
| 15 마이 변형 | (14와 동일; 게스트는 호출 안 함) | 게스트=로컬만 |
| 16 약관·정책 | — (`pictrip.org/legal/*` WebView) | API 아님(E2) |
| 셸/전역 | `POST /auth/logout`(로그아웃) · `DELETE /users/me`(탈퇴) · `GET /meta/version`·`/health` | — |

> **소비처 0 검증**: 위 표의 우측 엔드포인트 집합 = §3~§7의 라이브 엔드포인트 집합과 정확히 일치
> (역도 성립). 어떤 화면도 안 쓰는 라이브 엔드포인트 없음(honest-minimal, E1).

---

## 10. Reconcile 메모 (현 코드 → 이상형, 구현 = S10)

| 항목 | 현 코드 | 이상형(이 계약) | 조치 |
|---|---|---|---|
| OAuth 경로 | `/auth/oauth/kakao` 리터럴, 카카오만 | `/auth/oauth/{provider}` kakao·google·apple | 일반화 + google/apple OIDC 검증 추가(S10) |
| `GET /users/me` 필드 | `name`·`profileImageUrl` | `displayName`·`avatarUrl` | 직렬화 리네임(DB 컬럼 유지) |
| consents | `notification_consent` 존재 | drop(알림 비목표) | 컬럼 드롭(S7) + `PUT /users/me/consents` 신설 |
| saved 페이지네이션 | `limit`만(기본100/최대200), 플랫 리스트 | 커서+`limit`(기본24/최대60) + `meta.pagination` | 커서 인코딩·페이지네이션 메타 도입 |
| photo-search | `list[SimilarNeighbor]`, `limit`, distance만 | multipart+lat/lng, `{matches[],queryHadLocation}`, similarity 추가, 임계0.60·30 | 엔드포인트 재구성. `PhotoSearchResult` 폐기 |
| nearby | radius 기본 1000, `crowd`·`firstImage2Url` 포함 | radius 기본 3000, **`crowd` 제거 → `congestion` 재도입**(정정 S11 §7-A D1, 텍스트 칩), `firstImage2Url` 제거, region 메타·세분 라벨 | 기본값·필드 정리 + congestion 직렬화 |
| 혼잡도(congestion) | `spot_concentration` = `/spots/trending` 전용(엔드포인트 제거 예정) | canonical 카드 선택 필드 `congestion`(§1.3 버킷), feed·curation·detail·nearby·photo-search에서 데이터 있으면 채움 | `spot_concentration` JOIN 직렬화 추가(테이블 보존, 트렌딩 엔드포인트만 제거) |
| photo-search 임계 | (현 미적용) | 고정 0.60 → **캘리브레이션(FP/FN 교차)+top-N 소프트 플로어**(S11 §4 D3) | 임계 튜닝/플로어 로직 |
| refresh | (이상형에서 입력 그대로 에코) | **슬라이딩**: refresh를 새 exp=now+30d로 재민트(jti·claims 동일, 회전·도난탐지 없음, S11 §3 D4) | refresh 재민트 로직 |
| spot detail | `moods[]` 포함 | `moods[]` 제거 | 직렬화에서 제외 |
| 카드 `category` | by-region/batch만 채움 | 모든 카드 세분 `lcls_systm3_nm` | 조인 직렬화 통일(S7 §6) |
| 신규 엔드포인트 | 없음 | `/home/feed`·`/curations/{slug}`·`/map/regions-tree`·`PUT /users/me/consents` | 신설(curations 2테이블 = S7) |
| 제거 | search·trending·by-region·similar·related·moods·batch·regions·today-inspo·courses·notifications·analytics | 라우트+모듈 삭제 | 코드 제거 ↔ 마이그레이션 순서 = S10 |

---

## 11. 후속 위임

- **S8(인프라/캐시) — 완료**: Redis `curation:{id}:spots`(KST자정)·`regions:tree`(24h, centroid 런타임AVG 캐시)·`denyjti:{jti}` 덴리스트, AOF everysec; 딥링크 = Universal/App Links(공유 `https://pictrip.org/{spots|curations}/…` + 앱스킴 `pictrip://…`, deferred 없음); legal = Cloudflare Pages 정적. → `S08-infra.md`.
- **S10(reconcile·구현순서)**: §10 표 전체 적용 순서 — OAuth `{provider}` 일반화+카카오 OIDC 활성화, photo-search 재구성, saved 커서, nearby 정리, `displayName/avatarUrl` 리네임, 제거 라우트+모듈 삭제 ↔ Alembic 마이그레이션(curations 신설·드롭) 순서, 시드 스크립트, 전체 검증(`POSTGRES_DB=pictrip_test`).
