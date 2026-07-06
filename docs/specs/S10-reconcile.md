# S10 — Reconcile 종합 · 마이그레이션 · 구현 순서 (마스터 플랜)

> 세션 S10(마지막). 입력 SSOT: `session-context.md`(잠긴 결정·결정 로그 S1~S9·교차
> reconcile), 화면/설계 스펙 `screens/S01…S06`·`platform/S07…S09`, **현 코드(ground truth)** —
> `backend/app/{core,modules}`, `alembic/versions/*`(head=`0010`),
> `deploy/homeserver/{deploy.sh,docker-compose.prod.yml}`, `mobile/src/*`.
>
> **S10은 새 설계를 만들지 않는다.** S1~S9에서 모든 설계는 잠겼다. 이 문서는 그 reconcile
> 노트를 하나로 종합하고, **마이그레이션 ↔ 코드제거 ↔ 신규구현의 롤백 안전한 순서**를
> 형식화한다. 실제 구현은 이 문서를 입력으로 다음 단계에서 수행한다.

---

## 0. 검증된 기준점 (현 코드 실측 — 2026-06-20)

순서 설계가 걸려 있는 사실들을 코드에서 직접 확인했다(메모리/스펙 텍스트 아님):

| 사실 | 위치 | 함의 |
|---|---|---|
| **모듈 8개** (목표 6) | `app/modules/`: courses·images·map·**recommendations**·spots·system·taste·users | `courses`·`recommendations` 모듈째 제거 |
| **auth = 회전 기계 전체** | `app/core/auth.py`: `issue_token_pair`(rt:active+sess:+user:sessions ZSET), `rotate_refresh`(5키 Lua), `_revoke_family`/`revoke_session`/`revoke_all_user_sessions`, `rt:grace` | 전부 `denyjti:{jti}` 단일 키로 교체(S8 §2.2) |
| **Redis 풀 2개** | `app/core/redis.py`: `redis_cache`(decode=True, **recommendations 전용**) + `_redis`(lifespan, `RedisDep`, decode=False) | recommendations 제거 시 `redis_cache` 고아 → 단일 풀 통합 |
| **`_seconds_until_kst_midnight`** | `app/modules/recommendations/services.py:40` | `curation:{id}:spots` 일캐시(S8)가 재사용 → **모듈 삭제 전** `app/core`로 이관 |
| **compose Redis** | `deploy/homeserver/docker-compose.prod.yml:9` = `--save 60 1`만 | AOF everysec + maxmemory 256mb noeviction 추가(S8 §2.3) |
| **부팅 = `alembic upgrade head && uvicorn`** | compose `:30` | 모든 배포가 기동 시 마이그레이션 실행 |
| **롤백은 이미지만, 마이그는 안 됨** | `deploy.sh`: 스모크 실패 → `PREV_TAG` 재pull+`compose up`; 마이그는 forward-only | **롤백된 구 이미지가 새 스키마 위에서 돈다** → 파괴적 마이그는 롤백대상 이미지가 견뎌야 함 |
| Alembic head = `0010` | `alembic/versions/20260607_0010_drop_dead_tables.py` | 0010이 이미 15테이블 드롭(재드롭 불필요), 0005가 related/tats 드롭. S7 §현스키마 참조 |

이 마지막 두 줄이 S10 구현 순서의 **척추**다(§3).

---

## 1. Reconcile 종합표 (S1~S9 통합 — 현 코드 → 이상형)

영역별로 모든 diff를 통합하고 교차결정(C1·C2·B·D 계열)과 중복 제거했다. 각 행의 "단계"는
§3 구현 순서의 스테이지를 가리킨다.

### 1.1 DB (S7)

| 항목 | 현 코드 | 이상형 | 마이그 | 단계 |
|---|---|---|---|---|
| curations | 없음 | 신규 테이블(1급 엔티티) | **M1**(추가) | A |
| curation_spots | 없음 | 신규 테이블(손픽·순서) | **M1**(추가) | A |
| 랜덤풀 인덱스 | `idx_spots_active_region`(이미지 조건 못받침) | `idx_spots_image_pool (ldong_regn_cd) WHERE show_flag=1 AND first_image_url IS NOT NULL` | **M2**(추가) | A |
| `user_auth_providers.refresh_token_enc` | 컬럼 존재(죽음) | 드롭(덴리스트 전용) | **M3**(파괴) | B |
| `user_consents.notification_consent` | 컬럼 존재 | 드롭(알림 비목표) | **M3**(파괴) | B |
| `courses`·`course_days`·`course_items` | 존재 | 드롭(자식→부모) | **M4**(파괴) | B |
| `notifications` | 존재 | 드롭 | **M4**(파괴) | B |
| `analytics_events` | 존재 | 드롭 | **M4**(파괴) | B |
| `spot_concentration` | 존재 | **보존**(사용자 결정 — 엔드포인트만 제거) + **congestion 재융합 소스로 재사용**(S11 §7-A, D1: canonical 카드 `congestion` 직렬화가 content_id JOIN, 테이블·sync 스크립트 생존, 트렌딩 EP는 계속 제거) | 건드리지 않음 | — |
| curations CHECK `ck_curation_scope` | 없음 | `(type='region' AND region_cd IS NOT NULL) OR (type='mood' AND mood_id IS NOT NULL) OR type='editorial'` 명명 CHECK — M1에 **수동 추가**(S11 §5, D6) | **M1**(추가) | A |
| `users.profile_image_url` | 존재 | **재사용**(avatarUrl로 직렬화 노출, 컬럼 리네임 X) | 없음 | A |
| `user_consents.terms_version` | 존재 | **유지**(동의 버전 추적, 별도 이력 테이블 없음) | 없음 | A |
| 탈퇴 cascade | `user_saved_spots`·`user_consents`·`user_auth_providers` 전부 ON DELETE CASCADE 보유 | 그대로(앱레벨 추가삭제 불필요) | 없음 | — |

### 1.2 auth / Redis (S1·S8)

| 항목 | 현 코드 | 이상형 | 단계 |
|---|---|---|---|
| 인증 모델 | 회전+도난탐지(rt:active/deny/grace·sess:·user:sessions ZSET·5키 Lua) | `denyjti:{jti}` 단일 키. 발급=Redis 쓰기 0 / refresh=JWT검증+`EXISTS denyjti` / 로그아웃·탈퇴=`SET denyjti EX <남은 refresh TTL>` | A |
| refresh 회전 | `rotate_refresh`(새 토큰쌍 발급) | **회전 없음 + 슬라이딩**(S11 §3, D4 — 이전 "에코" 정정): 입력 refresh 검증 후 **exp 재민트**한 refresh + 새 access 반환(에코 폐기). single-flight(요청당 1회 갱신) | A |
| 덴리스트 조회 실패모드 | (회전=fail-closed) | **fail-open**(Redis 일시장애 시 통과) | A |
| access 즉시차단 | (없음) | 없음 유지(`get_current_user_id`=JWT 디코드만, 로그아웃=최대 15분 뒤 차단) | A |
| Redis 풀 | `redis_cache`(decode=True) + `_redis` 2개 | **`redis_cache` 제거 → 단일 lifespan 풀(`RedisDep`)** | A |
| KST자정 헬퍼 | `recommendations/services.py:40` | `app/core`로 이관(모듈 삭제 전) | A |
| Redis 영속성 | `--save 60 1` | + `--appendonly yes --appendfsync everysec` | A(compose) |
| Redis eviction | (무설정) | `--maxmemory 256mb --maxmemory-policy noeviction` | A(compose) |
| 캐시 키 신규 | — | `denyjti:{jti}`(refresh TTL)·`curation:{id}:spots`(KST자정 + **지터**, S11 §5/D6)·`regions:tree`(24h) | A |
| id_token 검증 | (카카오 access_token+`/v2/user/me`만) | **공급자별 id_token 검증**(S11 §3, D4): kakao·google·apple 각 JWKS·iss·aud·exp 검증 | A |
| 모바일 토큰 저장 | (현행 SecureStore 기본) | **SecureStore `WHEN_UNLOCKED_THIS_DEVICE_ONLY`**(S11 §3, D4) — refresh만, 백업·기기이전 차단 | M-2 |
| 갱신 동시성 | (현 single-flight) | **single-flight 유지**(S11 §3, D4) — 실패요청당 1회 refresh | A/M-2 |
| Redis 알림(pub) | — | **로그아웃·탈퇴 시 `denyjti` SET + Redis 알림**(S11 §3, D4) | A |

### 1.3 API 직렬화 (S9)

| 항목 | 현 코드 | 이상형 | 단계 |
|---|---|---|---|
| OAuth 경로 | `/auth/oauth/kakao` 리터럴(카카오 access_token+`/v2/user/me`) | `/auth/oauth/{provider}` kakao·google·apple, **3종 OIDC id_token 통일**(카카오 OIDC 활성화) | A |
| `GET /users/me` | `name`·`profileImageUrl` | `displayName`·`avatarUrl`(직렬화 리네임, DB 컬럼 유지) | A |
| consents | `notification_consent` 포함 | drop + 신규 `PUT /users/me/consents{locationConsent,photoConsent?,termsVersion}` | A(코드)+B(컬럼) |
| saved 페이지네이션 | `limit`만(기본100/최대200), 플랫 리스트 | 커서+`limit`(기본24/최대60) + `meta.pagination{nextCursor,hasMore,count}` | A |
| photo-search | `list[SimilarNeighbor]`(limit, distance만) | multipart+lat/lng → `{matches[+similarity,distance?,region메타],queryHadLocation}`, **임계 캘리브+소프트플로어**(S11 §2, D3 — 고정 ~0.60 대신 캘리브된 임계 + 소프트플로어로 0건 방지)·**유사도% 버킷 표시**·≤30·0건=빈200. **임베딩 백필 게이트**(커버리지 측정, §4). HNSW=**ANN-ORDER+LIMIT-then-join**(베이스 테이블 직접 ORDER+LIMIT 후 조인). `PhotoSearchResult`(무드검출) 폐기 | A |
| nearby | radius 기본 1000, `crowd`·`firstImage2Url` 포함 | radius 기본 3000, region 메타 + **세분 `lcls_systm3_nm`** 라벨 추가. **`crowd`→`congestion` 재도입**(S11 §7-A, D1 — 이전 "crowd 제거" 정정): `low`/`medium`/`high`/`null`, spot_concentration JOIN, v<34/34~66/>66 버킷 | A |
| spot detail | `moods[]` 포함 | `moods[]` 제거(`info_data` 미사용) | A |
| 카드 `category` | by-region/batch만 채움 | **모든 카드 세분 `lcls_systm3_nm`**(조인 `spots.lcls_systm3→lcls_systm3_cd`) | A |
| 카드 DTO(C1) | 혼재 | canonical `{contentId,title,firstImageUrl,category}` camelCase+KTO명(이미 일치, 신규 리네임 없음) + **선택 확장 `congestion: "low"\|"medium"\|"high"\|null`**(S11 §7-A, D1 — spot_concentration content_id JOIN; 직렬화 추가만, **DB 변경 없음 Stage A**) | A |

### 1.4 신규 엔드포인트 (S9)

| 엔드포인트 | 백킹 | 단계 |
|---|---|---|
| `GET /home/feed` (heroes6+rails3) | curations(type별 published) + curation_spots/**품질게이트 랭킹풀**(S11 §7-B, D2 — 랜덤 채움 정정; Stage A 직렬화/서비스 로직, 마이그 무관) | A |
| `GET /curations/{slug}` (region 전용) | curations(region) + curation_spots/**품질게이트 랭킹풀**(S11 §7-B, D2) | A |
| `GET /map/regions-tree` (17시도+시군구+centroid) | regions/sigungus + **centroid 런타임 AVG**(spots mapx/mapy) → `regions:tree` 캐시 | A |
| `PUT /users/me/consents` | user_consents upsert | A |

### 1.5 제거 (S9 §8) — 라우트 + 모듈

| 제거 | 사유 | 단계 |
|---|---|---|
| `/spots/search` | 텍스트검색 비목표/retired | A |
| `/spots/trending` | 트렌딩 비목표(테이블 `spot_concentration`은 보존) | A |
| `/spots/by-region` | 큐레이션 대체 | A |
| `/spots/{id}/similar`·`/related` | 화면 미소비(E1); 사진검색=photo-search, 주변=nearby | A |
| `/moods`·`/moods/{code}/spots` | 홈 무드레일=home/feed 대체 | A |
| `/spots/batch` | 소비처 없음(인라인 내려줌) | A |
| `/regions`(평면 17) | regions-tree 대체(E4) | A |
| `/recommendations/today-inspo` + **recommendations 모듈** | today-inspo 비목표(`_seconds_until_kst_midnight` 이관 후 삭제) | A |
| `/courses/*` + **courses 모듈** | 코스 일체 비목표 | A |
| `/me/notifications` | 알림 비목표(테이블은 M4) | A |
| `/analytics/events` | analytics 비목표(테이블은 M4) | A |

> **결과 = 6 모듈**(users·taste·spots·images·map·system). 코드 제거는 Stage A, 테이블 드롭은 Stage B.

### 1.6 모바일 (S1~S6)

| 항목 | 현 | 이상형 | 단계 |
|---|---|---|---|
| 테마 | 구 light-rose `Pt`(`theme.ts`) | 무채색 토큰(잉크/그레이, 로즈 금지) | M-1 |
| 홈 소스 | 하드코딩 무드 레지스트리 | `/home/feed` fetch 전환 | M-2 |
| 화면 | 구 15화면 | 목업 16화면 재구축(셸=4탭+사진 모달런처, S1 §5.1) | M-2 |
| API 클라 | 구 DTO | canonical 카드·displayName/avatarUrl·saved 커서·photo-search·nearby·regions-tree·consents·oauth `{provider}` | M-2 |
| 거리 util | 분산 | `formatDistance(m)` 단일(C2): `<1km {정수}m`/`1–10km 소수1 km`/`≥10km 정수 km` | M-2 |
| 딥링크 | 없음 | iOS associated domains `applinks:pictrip.org` + Android intent-filter `autoVerify` + 스킴 `pictrip://`(엔타이틀먼트/매니페스트, **네이티브 모듈 아님**). 연결파일 = **assetlinks 지문 2개**(debug+release SHA-256)·**AASA `components`**·**웹 폴백 페이지**(S11 §4, D5) | M-3 |
| 이모지(D1)·홈푸터 문의(D2) | 존재 | 제거(라인-SVG `<Icon>`) | M-2 |

### 1.7 인프라 (S8)

| 항목 | 현 | 이상형 | 단계 |
|---|---|---|---|
| 토폴로지 | CT112(api+redis+tunnel+runner)/CT110(pg)/CT111(pipeline) | 현행 유지 + **apex `pictrip.org`=Cloudflare Pages** 신규 1컴포넌트 | CF |
| legal | `#14` stub | CF Pages 정적 4페이지(무채색) + 인앱 WebView | CF |
| 딥링크 연결파일 | 없음 | CF Pages `/.well-known/AASA`(무확장자 `application/json`, **`components` 포함**)+`assetlinks.json`(**지문 2개**: debug+release SHA-256) + 리다이렉트 Function + **웹 폴백 페이지**(앱 미설치 UA) (S11 §4, D5) | CF |
| CI/CD | backend push-main 자동·mobile `v*`→EAS | 현행 + CF Pages 네이티브 Git연동(워크플로 0) + CT112 디스크 prune 주간 systemd timer | A/CF/운영 |

---

## 2. Alembic 마이그레이션 플랜 (4 리비전, head `0010` 위)

원칙: `POSTGRES_DB=pictrip_test`로 리비전 생성·`upgrade head`·`downgrade` 검증(라이브
`pictrip` 금지). autogenerate는 **부분 인덱스 술어·명명 CHECK·드롭 downgrade**를 놓치므로
생성 SQL을 **반드시 수동 검토**. CHECK는 반드시 명명(`ck_*`)(익명은 추적 불가).

### M1 — `xxxx_curations` (추가, Stage A 배포에 포함)

`create_table('curations')` + `create_table('curation_spots')`.

- **수동 확인 필수**:
  - `ck_curation_type` CHECK `type IN ('region','mood','editorial')` — 명명.
  - **`ck_curation_scope` CHECK**(S11 §5, D6 — 수동 추가): `(type='region' AND region_cd IS NOT NULL) OR (type='mood' AND mood_id IS NOT NULL) OR type='editorial'`. 명명(익명 금지), autogenerate가 못 emit → `op.create_check_constraint('ck_curation_scope','curations', ...)` 수동 작성. (아래 "부분 CHECK 미적용" 노트를 이 제약이 대체 — region_cd↔type 정합을 DB가 강제.)
  - `curations.slug` UNIQUE.
  - `idx_curations_feed (type, is_published, position)` — `/home/feed` 핵심 경로.
  - `idx_curation_spots_order (curation_id, position)` — 손픽 정렬 읽기.
  - FK ondelete: `cover_spot_id`→spots **SET NULL**, `curation_spots.curation_id`→curations
    **CASCADE**, `curation_spots.content_id`→spots **CASCADE**. `ForeignKey(ondelete=...)`로
    선언하면 DDL emit됨(검증). `region_cd`→regions, `mood_id`→moods(NULL 허용, 풀 스코프).
- **컬럼명**: `curation_spots.content_id`(canonical `contentId` 일치 — 스케치 `spot_id` 폐기).
- ~~**부분 CHECK 미적용**(region_cd↔type 정합은 시드 스크립트/앱 책임, v1).~~ → **정정**(S11 §5, D6): `ck_curation_scope`로 DB가 직접 강제(위 수동 확인 항목).
- **downgrade**: `drop_table('curation_spots')` → `drop_table('curations')`.
- DDL 상세 = S7 §3.1·§3.2.

### M2 — `xxxx_spots_image_pool_idx` (추가, Stage A 배포에 포함)

부분 인덱스 `idx_spots_image_pool (ldong_regn_cd) WHERE show_flag=1 AND first_image_url IS NOT NULL`.

- **autogenerate가 술어를 reflect 못 함**(Alembic #750/#155) → `op.create_index(..., postgresql_where=sa.text("show_flag = 1 AND first_image_url IS NOT NULL"))` **수동 작성**(repo의 trgm GIN 0008과 동일 패턴).
- **downgrade**: `op.drop_index('idx_spots_image_pool', table_name='spots')`.

### M3 — `xxxx_drop_dead_columns` (파괴, Stage B 배포)

- `op.drop_column('user_auth_providers', 'refresh_token_enc')`.
- `op.drop_column('user_consents', 'notification_consent')`.
- **downgrade**: 두 컬럼 재추가(`add_column`, nullable/default 원형 복원 — autogenerate가 add는 정상 emit).
- ⚠️ **Stage B 게이트**: 이 드롭은 Stage A 이미지(이 컬럼들을 ORM에서 이미 제거·미참조)가
  라이브가 된 뒤에만 안전(§3 expand/contract).

### M4 — `xxxx_drop_nongoal_tables` (파괴, Stage B 배포)

- `drop_table('course_items')` → `drop_table('course_days')` → `drop_table('courses')`
  (자식→부모) → `drop_table('notifications')` → `drop_table('analytics_events')`.
- **`spot_concentration` 건드리지 않음**(보존).
- autogenerate는 드롭 테이블의 **downgrade(재생성) DDL은 정상 emit**하나 **중복 `drop_index` 과생성** 가능 → 정리. (rename은 없음 — drop+add 합치기 불필요.)
- **downgrade**: 부모→자식 순 재생성(FK 순서).
- ⚠️ **Stage B 게이트**: Stage A 이미지가 courses·notifications·analytics 모듈/모델을 이미
  제거(테이블 무참조)한 뒤에만 드롭(orphan 테이블은 무해, 드롭은 롤백 비가역).

### 시드 스크립트 (마이그레이션 아님 — 코드/데이터)

- M1 적용 후 실행. region 6 + mood 3 큐레이션: 카피(S2 히어로 6 verbatim, B3 레지스트리)·
  `slug`·`cover_spot_id`·`is_published=true`·`position`. **초기 손픽 비움 → 랜덤 운영**(테마일치
  풀, 결정적 seed, 일캐시) → 이후 손픽 적재(데이터만, 무마이그).
- 위치: `backend/scripts/`(기존 sync 스크립트 컨벤션). 시드 없으면 `/home/feed`가 빈
  heroes/rails → **Stage A 배포 직후 시드 실행 필수**(모바일이 홈 의존 전).

> **autogenerate 한계 요약**: 부분 인덱스 술어(M2)·명명 CHECK(M1: `ck_curation_type`+`ck_curation_scope`)는 수동, 드롭 downgrade(M3·M4)는
> 검토 후 중복 정리. `alembic check`는 trgm GIN(0008 raw-SQL)을 원래 플래그함 — **CI 게이트는
> `upgrade head`이지 `check` 아님**(CLAUDE.md). 신규 부분/CHECK도 같은 사유 → 수동 검토로 처리.

---

## 3. 구현 순서 (핵심 — 배포/롤백 경계 명시)

### 3.1 척추 원칙 — expand → contract (롤백 안전성)

`deploy.sh`는 스모크 실패 시 **이전 이미지로 롤백하지만 마이그레이션은 되돌리지 않는다**
(forward-only). 롤백된 구 이미지도 부팅 시 `alembic upgrade head`를 다시 돌리고(이미 head라
no-op) **새 스키마 위에서** 구 코드가 실행된다. 따라서:

> **모든 파괴적 마이그레이션은, 그 컬럼/테이블을 더는 참조하지 않는 코드가 라이브가 되어
> 롤백 대상이 된 이후에만 적용한다.** (= expand/contract, 단일 홈서버의 유일한 롤백 안전 경로.)

- **추가형(M1·M2)**: 구 코드가 무시 → 어느 배포에서나 안전. Stage A 배포에 포함(부팅 시
  `upgrade head`가 curations 생성 후 uvicorn 기동 → 신규 코드가 curations 사용 가능).
- **파괴형(M3·M4)**: Stage A 이미지가 해당 컬럼/테이블 무참조 상태로 **그린·롤백대상**이 된
  뒤, **별도의 Stage B 배포**로 적용. orphan 테이블/컬럼은 그 사이 무해.
- (기각) 드롭을 코드제거와 한 배포에 묶기 → 그 배포 스모크 실패 시 안전한 롤백 대상 없음
  (구 이미지 + 잘린 스키마). **채택 안 함.**

### 3.2 백엔드 — Stage A (코드 빌드아웃 + 코드제거, 스키마는 추가형만)

**한 이미지 = 한 배포.** 마이그 세트 = base + M1 + M2(추가형). 드롭 없음.

작업(순서는 한 PR/이미지 내):
1. `_seconds_until_kst_midnight` → `app/core`(예 `app/core/time.py`)로 이관.
2. **auth.py 덴리스트 재작성**: `issue_token_pair`(Redis 쓰기 0)·refresh(JWT검증+`EXISTS denyjti`, fail-open, 회전 없음 + **슬라이딩 exp 재민트**(S11 §3/D4 — 에코 폐기)·single-flight)·logout(`SET denyjti EX <남은 refresh TTL>` + Redis 알림)·탈퇴(denyjti+cascade)·**공급자별 id_token 검증**(kakao/google/apple JWKS·iss·aud·exp). **제거**: `rotate_refresh`·`_revoke_family`·`revoke_session`·`revoke_all_user_sessions`·rt:active/sess/user:sessions/grace. auth 테스트 재작성.
3. **OAuth `{provider}` 일반화** + kakao/google/apple OIDC id_token 검증(카카오 access_token+`/v2/user/me` 폐기).
4. **Redis 풀 통합**: `redis_cache` 제거, 잔존 소비를 `RedisDep`/`_redis`로.
5. **신규 엔드포인트**: `/home/feed`·`/curations/{slug}`·`/map/regions-tree`·`PUT /users/me/consents`(curations 테이블=M1 이미 존재).
6. **직렬화 변경**: displayName/avatarUrl·saved 커서+pagination·**photo-search 재구성**(S11 §2/D3: 임계 캘리브+소프트플로어·유사도% 버킷·HNSW ANN-ORDER+LIMIT-then-join·임베딩 백필 게이트)·nearby(radius 3000·**`crowd`→`congestion` 재도입** S11 §7-A/D1·세분 라벨+region 메타)·spot detail moods[] 제거·카드 category 세분 조인 통일·**canonical 카드 `congestion` 직렬화**(spot_concentration content_id JOIN, DB 변경 없음)·**큐레이션 품질게이트 랭킹**(S11 §7-B/D2, 랜덤 채움 대체)·**캐시 지터+on-publish 무효화**(S11 §5/D6).
7. **라우트+모듈 제거**(§1.5): recommendations(헬퍼 이관 후)·courses 모듈째 + search·trending·by-region·similar·related·moods·batch·regions·notifications·analytics 라우트. ORM 모델에서 `refresh_token_enc`·`notification_consent`·courses/notifications/analytics 모델 **참조 제거**(테이블은 아직 DROP 안 함 — orphan 무해).
8. **compose Redis 플래그**: `--appendonly yes --appendfsync everysec --maxmemory 256mb --maxmemory-policy noeviction`(`deploy/homeserver/docker-compose.prod.yml`). Stage A 배포의 `compose up`이 적용.

**배포 경계**: 머지 → push-to-main → 자동배포(`alembic upgrade head`로 M1·M2 적용 → uvicorn).
스모크 그린 → **이 이미지가 롤백 대상**(이후 Stage B의 안전 기반). 시드 스크립트 즉시 실행.

**롤백 가능성**: Stage A 스모크 실패 시 pre-A 이미지로 롤백 → pre-A 코드는 M1·M2(추가형)
스키마를 무시 → 정상. **안전.**

### 3.3 백엔드 — Stage B (파괴적 드롭, A 그린 이후)

마이그 세트에 **M3 + M4** 추가. 앱 코드는 Stage A와 동일(마이그 파일만 추가).

**배포 경계**: push-to-main → `upgrade head`가 M3(컬럼 드롭)·M4(테이블 드롭) 적용. 스모크 그린.

**롤백 가능성**: Stage B 스모크 실패 시 Stage A 이미지로 롤백 → A 코드는 이미 드롭된 컬럼/
테이블 무참조 → 정상(드롭은 비가역이나 A가 견딤). **안전.** (진짜 비상 복구는 M3/M4
downgrade 또는 pg_dump.)

### 3.4 모바일 (별 트랙, `v*` 태그 → EAS; 백엔드 Stage A 라이브 이후)

1. **M-1 테마**: `theme.ts` 무채색 토큰 재작성.
2. **M-2 화면+클라**: 목업 16화면 재구축(셸 4탭+사진 모달런처)·홈 fetch 전환·API 클라(canonical 카드·displayName/avatarUrl·saved 커서·photo-search·nearby·regions-tree·consents·oauth `{provider}`)·`formatDistance`·이모지/문의 제거.
3. **M-3 딥링크**: `app.json` associated domains + Android intent-filter `autoVerify` + 스킴 `pictrip://`(엔타이틀먼트/매니페스트 — 새 네이티브 모듈 아님). Expo Router 라우팅 연결.

**경계**: 백엔드 Stage A 엔드포인트가 라이브여야 모바일이 가리킬 대상이 존재. TestFlight `v*`
태그 배포. M-3 딥링크 연결파일(AASA/assetlinks)은 §3.5 CF Pages와 짝(EAS Team ID·bundle·SHA-256).

### 3.5 Cloudflare Pages (별 트랙, 홈서버 무의존)

- `web/` 폴더: legal 4페이지(무채색 HTML)·`/.well-known/AASA`(무확장자 `application/json`, `_headers` MIME 강제)·`assetlinks.json`·리다이렉트 Function(`functions/spots/[id].js` 등 UA감지→스토어).
- CF Pages 네이티브 Git 연동(repo 연결, `web/` 루트). 워크플로 0.
- **legal 페이지는 언제든**(EAS 무의존). **`.well-known` 연결파일은 모바일 빌드 자격 필요**
  (AASA=Apple Team ID+bundle id, assetlinks=앱 서명 SHA-256) → M-3 빌드 후.

### 3.6 운영 (별 트랙)

- CT112 디스크 prune 주간 systemd timer(`docker image prune -af && docker builder prune -af`).
- 시드 스크립트 실행(Stage A 직후, §2).

### 3.7 순서 요약 (의존 그래프)

```
[M1·M2 추가형]
      └─▶ Stage A (백엔드 코드: auth 덴리스트·OAuth {provider}·풀통합·신규EP·직렬화·코드제거·compose)
              │   ▲ 배포·스모크 그린 = 롤백 대상 확정
              ├─▶ 시드 스크립트(region6+mood3)
              ├─▶ Stage B (M3 컬럼드롭 + M4 테이블드롭)   ← A 그린 이후만
              └─▶ 모바일 M-1→M-2→M-3 (A 엔드포인트 라이브 후)
                          └─▶ CF Pages .well-known (M-3 EAS 자격 후)
[CF Pages legal] ───────────────────────────────── 무의존, 아무때나
[운영: 디스크 prune timer] ───────────────────────── 무의존, 아무때나
```

---

## 4. 검증 게이트 (단계별)

매 단계 종료 시 통과해야 진행:

| 단계 | 게이트 |
|---|---|
| M1·M2 | `POSTGRES_DB=pictrip_test alembic upgrade head` + `downgrade -1`×N 왕복 그린; 생성 SQL 수동검토(부분 인덱스 술어·명명 CHECK `ck_curation_type`+`ck_curation_scope`·FK ondelete) |
| Stage A (백엔드) | `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && POSTGRES_DB=pictrip_test uv run pytest`(auth 테스트 재작성 포함); 배포 후 `/health` 로컬+공개 스모크 |
| Stage A — photo-search (S11 §2, D3) | `EXPLAIN (ANALYZE)` 출력에 **HNSW Index Scan** 노드 확인(seq scan 아님 — ANN-ORDER+LIMIT-then-join이 인덱스를 탔는지); **임베딩 커버리지% 측정**(백필 게이트 — `count(embedding)/count(*)`); 캘리브 임계+소프트플로어로 대표 쿼리 0건 미발생 확인 |
| Stage A — congestion (S11 §7-A, D1) | nearby/카드 응답에 `congestion` 필드 존재·spot_concentration JOIN 동작(v<34/34~66/>66 버킷); 트렌딩 EP 부재 확인(404) |
| 시드 | `/home/feed`가 heroes6+rails3 반환(빈 아님) 수동 확인 |
| Stage B | `POSTGRES_DB=pictrip_test alembic upgrade head`(M3·M4) + `downgrade` 왕복; 동일 backend 스위트; 배포 스모크 |
| 모바일 M-1~M-3 | `cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test`; iOS 시뮬 스모크(홈 fetch·로그인·사진검색·지도·저장·딥링크 진입) |
| CF Pages | legal 4페이지 200; **`curl -I` AASA = 200·`Content-Type: application/json`(무확장자)·리다이렉트 없음(no-redirect)**(S11 §4, D5); AASA `components` 필드 존재; assetlinks 지문 2개(debug+release) 포함; 리다이렉트 UA 분기 + 웹 폴백 페이지 |
| 딥링크 검증 (S11 §4, D5) | Android `adb shell pm get-app-links <pkg>` → 도메인 `verified`; iOS associated domains 진입 동작; 앱 미설치 시 웹 폴백 페이지 표시 |
| 통합 | `/verify`(backend+mobile 전체) 그린 + 시뮬 스모크 체크포인트 |

- 백엔드 마이그·테스트는 **항상 `POSTGRES_DB=pictrip_test`**(라이브 `pictrip` 금지 — 글로벌
  카운트 assert 깨짐). CI는 fresh `pictrip_test` + `upgrade head` + pytest.
- `lefthook` pre-commit이 ruff/prettier 자동수정(푸시 게이트 없음) — CI가 전부 재실행.

---

## 5. 잔여 충돌 노트 (S1~S9 스캔)

전 스펙을 교차 대조한 결과 **하드 모순은 없음**(C1 카드 DTO·C2 거리 util·consent boolean·
centroid 런타임 AVG·subtitle 정책 모두 정합). **S11 정정 반영**(refresh 에코→슬라이딩, crowd→congestion).
기록용 비충돌 사항:

1. **`dist` vs `distance` (의도된 것 — 버그 아님)**: `/map/nearby`는 `dist`, `/taste/photo-search`는
   `distance`로 같은 "미터" 값을 다른 필드명으로 내림(S9 §1.3 카드 확장표). 클라 `formatDistance(m)`가
   둘 다 먹으므로 reconcile 불필요. **통일하지 않음**(사용자 확인 2026-06-20).
2. **`category` 데이터-계약 갭(알려진 reconcile, 충돌 아님)**: 현 `/map/nearby`는 coarse 버킷을
   `category`로 내림 → 이상형은 카드 라벨=세분 `lcls_systm3_nm`. **DB 변경 아님**(컬럼·조인
   이미 존재) → 직렬화만 추가(Stage A §3.2-6). 칩 필터 버킷(6 coarse)은 별개 유지.
3. **HNSW JOIN/CTE 미사용 함정(기술 제약, S7 §10)**: 사진검색·유사도는 `ORDER BY embedding
   <=> $1::halfvec(512)`를 **spots 베이스 테이블 직접**에 걸어 HNSW를 태운 뒤 부가 조인 적용.
   photo-search 재구성(Stage A §3.2-6) 시 쿼리 형태 주의(설계 결정 아님 — 구현 주의).
4. **`/auth/refresh` 응답에 `user` 포함**(S9 §3.2): 스플래시 silent refresh도 user 룩업 1회
   동반 — 정상(스키마 재사용). 충돌 아님.
5. **`_seconds_until_kst_midnight` 이관 의존성**: recommendations 모듈 삭제 전 `app/core`로
   이동 필수(§0·§3.2-1) — 순서 의존이지 충돌 아님.
6. **`crowd`→`congestion` 재도입(의도된 정정 — 버그 아님)**: S11 §7-A/D1이 이전 "crowd 제거"를
   뒤집어 canonical 카드·nearby에 `congestion`(low/medium/high/null, spot_concentration JOIN)을
   재도입. 테이블·sync 스크립트 보존과 정합(트렌딩 EP만 계속 제거) — DB 변경 없는 Stage A 직렬화 추가.

---

## 부록 — 다음 단계 입력

이 문서는 구현 세션의 입력이다. 권장 진행: **Stage A(백엔드)부터 TDD/subagent-driven**으로
한 PR씩(auth 덴리스트 → OAuth → 풀통합/제거 → 신규EP/직렬화), M1·M2 추가형 마이그 동반.
A 그린·시드 후 Stage B(드롭) 별도 PR/배포. 모바일·CF Pages는 병렬 트랙. 커밋/푸시는 사용자
요청 시에만. `docs/specs/`는 병렬 세션 충돌 점검(편집 전 재확인, 커밋 전 `git status`).
