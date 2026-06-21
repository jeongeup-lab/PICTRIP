# PicTrip 리팩토링 — 세션 공통 컨텍스트

> 모든 설계 세션이 **가장 먼저 읽는** 파일. 잠긴 결정 · 지울 수 없는 제약 ·
> 세션 로드맵 · 결정 로그를 담는다. 각 세션은 fresh context에서 시작하므로,
> 여기와 자기 프롬프트에 적힌 입력만 신뢰한다.

## 작업 방식

- 한 세션 = 한 관심사. 그 하나를 **완벽히** 정하고 spec 파일을 쓴 뒤 종료한다.
- 모든 세션은 `superpowers:brainstorming` 스킬로 시작한다. 한 번에 한 질문씩,
  근거를 파고들어 결정한다. 대충 종합하지 않는다.
- 설계 철학(브리프): **화면/UX/네비/ API 형태는 백지에서 이상적으로** 설계한다
  (기존 코드에 맞추지 않는다). **단 DB·인프라는 "이상 설계 → 현실 reconcile"**.
- 산출물: `docs/specs/<group>/S<nn>-<slug>.md` (group: `screens`·`platform`·
  `enhancements`·`admin`, nn=제로패딩). 끝나면 이 파일의 **결정 로그**에
  한 줄 추가하고 커밋한다.
- 입력 SSOT: 디자인=`docs/mockups/`(무채색 16화면, `index.html` 갤러리),
  제약=`CLAUDE.md`(루트), 브리프=`docs/specs/_context/design-brief.md`.

## 잠긴 결정 (이미 사용자 승인 — 재논의 금지, 세부만 설계)

1. **큐레이션 = 1급 엔티티.** `curations` + `curation_spots` 테이블. region/mood/
   editorial 3종을 한 구조로. 홈 히어로 = published region 큐레이션, 무드 레일 =
   mood 큐레이션. 카피/표지/스팟순서는 DB 적재(시드 스크립트). 표지는 spot의 KTO
   URL 참조(다운로드 없음).
2. **홈 = 백엔드 주도.** `/home/feed`가 히어로+레일을 서버에서 조립 → 앱 재배포
   없이 편성 교체. 모바일 features/home 하드코딩 레지스트리를 fetch로 전환.
3. **사진 검색 = 유사도 + 거리순.** `/taste/photo-search`에 선택적 lat/lng 전달 →
   결과에 distance 포함 → 클라이언트 정렬칩. GPS 동의 시에만 거리칩 활성.
4. **인증 = 3종 계약(kakao·google·apple), lean 구현.** id_token(OIDC) 검증 →
   자체 JWT(access=메모리, refresh=secure-store) 발급 + refresh 회전. **세션/디바이스
   테이블 폐기, Redis jti 덴리스트로만 로그아웃/탈퇴 폐기.** 현재 카카오 인증의
   over-engineering(sessions/devices, refresh_token_enc, 세션폐기 머신)을 단순화.

## 지울 수 없는 자산 / 제약 (reconcile 대상)

- 프로덕션 DB: `spots ~68k` + CLIP 임베딩 `~64%`(`spot_embeddings`, halfvec(512),
  HNSW). **새 스키마는 이 위에 얹는다 — 자산 폐기 금지, 매핑/마이그레이션 경로 명시.**
- KTO 컴플라이언스: 이미지 다운로드/저장 금지(URL만), `overview` verbatim,
  임베딩 `halfvec(512)`(`... <=> $1::halfvec(512)` 캐스팅).
- 인프라: Proxmox 홈서버(FastAPI+Redis CT112, Postgres CT110), Cloudflare 터널
  `https://api.pictrip.org`, GitHub Actions + self-hosted runner, GHCR. **No AWS.**
- 모바일 네이티브: 지도=KakaoWebMap(WebView+JS SDK), `@react-native-kakao/map` 뷰
  금지. Expo SDK 56 네이티브 핀 고정. 새 네이티브 모듈 추가 금지. 무채색(잉크/그레이,
  로즈 금지). access=메모리/refresh=secure-store.
- 백엔드 모듈 6개: `users · taste · spots · images · map · system`. (courses·
  recommendations 제거.)

## 비목표 (설계에 넣지 않음 — 확정)

코스 일체 · 텍스트검색(`/spots/search`) · 트렌딩(`/spots/trending`)+`spot_concentration` ·
크라우드/혼잡도 배지(무채색 목업에 없음) · today-inspo · 알림(`/me/notifications`) ·
analytics 이벤트 · `/spots/by-region`(큐레이션이 대체).

## 세션 로드맵 (이 순서로 진행 — 화면 → DB → 인프라 → API → reconcile)

| 세션 | 스코프 | 목업 | 산출물 |
|---|---|---|---|
| S1 | 진입 퍼널 (스플래시·온보딩·로그인·권한) | 01·02·03·04 | `screens/S01-onboarding-auth.md` |
| S2 | 홈 + 큐레이션 상세 | 05·06 | `screens/S02-home-curation.md` |
| S3 | 스팟 상세 | 07 | `screens/S03-spot-detail.md` |
| S4 | 사진 검색 플로우 | 08·09·10 | `screens/S04-photo-search.md` |
| S5 | 지도 + 지역 선택 | 11·12 | `screens/S05-map-region.md` |
| S6 | 저장·프로필·상태·약관 | 13·14·15·16 | `screens/S06-profile-legal.md` |
| S7 | DB 설계 (전 화면 종합) | — | `platform/S07-db.md` |
| S8 | 인프라 설계 | — | `platform/S08-infra.md` |
| S9 | API 계약 (화면→엔드포인트) | — | `platform/S09-api-contract.md` |
| S10 | Reconcile 노트 + 마이그레이션 + 구현순서 | — | `platform/S10-reconcile.md` |

각 화면 세션 본문에 명세할 것: 목적 · 구성요소 · 상태(loading/normal/empty/error) ·
데이터 needs(비공식 스케치) · 진입/이탈 네비 · 인터랙션 · 빈/에러 구분.
DB/인프라/API 세션은 화면 세션들의 data needs를 종합해 형식화한다.

## 결정 로그 (각 세션 종료 시 한 줄 추가)

- **S1 (2026-06-20) 진입 퍼널** → `S01-onboarding-auth.md`.
  게스트-우선 최소마찰: 스플래시(flag+silent refresh 병렬 hydrate, 실패=조용한
  게스트 강등) → 온보딩 1회(`onboarding_seen` AsyncStorage, CTA/건너뛰기 시 세팅)
  → CTA는 사진선택(08) 직행/건너뛰기는 홈. 로그인·권한은 트리거 기반(로그인 필요=
  스크랩·마이 탭). 로그인=단일 컴포넌트(시트/풀스크린), 3종 OIDC id_token 통일,
  성공 시 보류 액션 재개; sessions/devices 폐기·Redis jti 덴리스트·refresh 회전.
  권한=priming(undetermined)/denied 2상태, granted 통과. consent=게스트는 OS권한만,
  로그인 직후 스냅샷 upsert+포그라운드 재동기화. → S10 reconcile: 카카오 OIDC 활성화,
  AppState 권한 재체크 feature, 기존 카카오 인증 over-engineering 제거.
- **S4 (2026-06-20) 사진 검색(08·09·10)** → `S04-photo-search.md`.
  네비=독립 탭 아님, push/modal 스택(08→09→10→07상세), 09→10은 replace. KTO 폐기=
  불변규칙(메모리 추론·즉시 폐기, 화면 문구 없이 약관+스펙에만 명시). 08=빈 플레이스
  홀더+촬영/갤러리(갤러리는 시스템 선택창=권한팝업 없음, 촬영만 just-in-time), CTA는
  사진 있어야 활성. 09=indeterminate(min~600ms), ←=요청 abort 후 08, 실패=인라인
  오류(다시시도/돌아가기), 0건은 실패 아님. 위치=흐름 중 팝업 금지·이미 허용된
  last-known만 첨부. 10=클라 재정렬(유사도순 기본/거리순), 무GPS면 정렬칩 줄+거리
  텍스트 숨김, 유사도 임계값(~0.60 튜닝)+상위N(~30) 미달시 빈상태[다른 사진으로],
  카드 탭→07(인라인 저장 없음). 후속: 진입점=S2, API 형식=S9, 상세=S3.
- **S6 (2026-06-20) 저장·프로필·상태·약관(13·14·15·16)** →
  `S06-profile-legal.md`. 약관 4문서=자체도메인
  `pictrip.org/legal/{slug}` 정적 페이지+인앱 WebView(백엔드 테이블/번들 둘 다 없음;
  스토어·OAuth가 요구하는 정책 URL 재사용; 데이터출처=KTO 고지 callout). 스크랩 해제=
  낙관적 즉시 제거+실행취소 토스트(서버 실패 롤백). 게스트 하트=로그인 시트→로그인(03)→
  복귀 후 수동 재탭(pending intent 없음). 위치권한 행=상태표시+탭→OS설정. 로그아웃=
  확인 Alert→게스트 변형(refresh jti 덴리스트). 회원탈퇴=이중 Alert→cascade 삭제
  (users·user_saved_spots·user_consents·user_auth_providers)+토큰 덴리스트. 프로필=
  OAuth 이름·이메일·아바타URL(URL 참조만, 모노그램/‘여행자’/공급사 라벨 폴백). 13 그리드는
  14 전체보기로만 진입(항상 로그인), 그리드 내 전부 해제 시 인라인 빈 상태(자동 pop 없음).
  reconcile: user_saved_spots 재사용·users.avatar_url(nullable,URL) 추가·약관 테이블
  불필요·동의 버전 추적은 S1 이월·호스팅 방식은 S8. 후속: 계약=S9.
- **S5 (2026-06-20) 지도+지역선택(11·12)** → `S05-map-region.md`.
  단일 점+반경 쿼리(`/map/nearby?lat&lng&radius&category`, region 파라미터 없음,
  반경 3km 고정, 거리순 30개). 패닝은 침묵·"이 지역에서 검색" 탭해야 재조회+라벨 갱신.
  헤더 라벨은 GPS일 때만 `현위치` 접두사, 지역선택/패닝검색 후 접두사 제거. GPS 없음/거부
  =서울 시청 중심+비차단 배너(지도 정상). 바텀시트 3-스냅(peek/half/full). 카테고리 칩
  단일선택(NearbyCategory 1:1). 지역 피커=dim+62%시트 2단 단일선택, `검색` CTA 명시 적용→
  시군구 centroid로 재센터. reconcile: nearby `crowd` 필드 제거(배지 없음), 시군구 centroid
  는 스팟 mapx/mapy 평균 파생(Sigungu 좌표 컬럼 없음), `regions-tree` 신규. 후속: centroid
  사전계산 vs 런타임=S7, API 형식=S9.
- **S2 (2026-06-20) 홈+큐레이션 상세(05·06)** → `S02-home-curation.md`.
  `/home/feed` 고정 6 region 히어로 + 3 mood 레일(개수 불변, 서버가 슬롯 교체). 스팟
  소스=`curation_spots` 손픽(1급), 비면 테마-일치 랜덤(region→지역, mood→`spot_moods`,
  KTO 이미지 조건, curation별 seed·일 캐시)→나중에 손픽이 덮어씀. 표지=`cover_spot_id`
  FK→firstimage 해석(+curation_spots[0] 폴백, 다운로드 X). 편집필드=title·subtitle·lead·
  intro·cover_spot_id·ordered spots(eyebrow 없음, title 줄바꿈 verbatim). 히어로=수동
  스와이프+스냅+6분할 인디케이터, 자동전환 없음. 상세 더보기=intro 3줄 클램프 펼침/접기.
  mood=홈 레일 인라인 전용(상세 없음·헤더 비탭·카드→07); 06 상세는 region 전용. 레일 8·
  상세 그리드 8(payload=hero6 커버만+rail3×8). 상태=레이아웃 스켈레톤+inset-gray 이미지
  폴백+홈 풀화면 재시도/pull-refresh+상세 재시도/404. reconcile: 신규 `curations`·
  `curation_spots`, 재사용 spots·spot_images(firstimage)·spot_moods·regions/sigungus,
  홈 하드코딩 레지스트리→fetch 전환. 후속: DDL=S7, 딥링크/캐시=S8, 계약=S9.
- **S3 (2026-06-20) 스팟 상세(07)** → `S03-spot-detail.md`.
  세로 1화면, 게스트 열람·저장만 인증. 스크롤=히어로 컨트롤 사라지고 제목이 상단
  지나면 흰 스티키 헤더 크로스페이드(뒤로+잘린제목+저장, 공유 없음). 저장 3곳(히어로
  우상단·스티키·'방문 예정?' 인셋) 단일 토글 동기화·공유 1곳(인셋만). 히어로 한 줄
  설명(teaser) **제거**(KTO 태그라인 부재·verbatim 정직성·레이아웃 안정성; overview
  첫문장/큐레이션카피 안 씀), 서브라인=`category·region sigungu`. 소개=`overview`
  verbatim 4줄 클램프+인라인 더보기/접기(null이면 섹션 숨김). 메뉴=음식점
  (`firstmenu‖treatmenu` 존재)만 '소개' 바로 아래, firstmenu→칩/treatmenu→텍스트(messy
  정리 허용). 위치=KakaoWebMap 정적 미리보기(핀·탭→카카오 외부)+네이버/카카오 좌표
  딥링크+웹 폴백(lat=mapy,lng=mapx)+정보행 4(주소복사/시간 usetime/전화 tel→infocenter
  폴백·다이얼/홈페이지 URL파싱·외부, null행 숨김, 휴무·주차 미표시). 갤러리=`images[]`
  스트립(히어로 배경 firstImage 별도), "전체 사진 {n}"=심플 스와이프 페이저(n/총장·탭/
  아래스와이프 닫기·줌X), images 0장이면 스트립·버튼 숨김. 주변 둘러보기=`/map/nearby`
  단일 레일(자기 제외, 사진+이름+세분 카테고리). 게스트 저장=로그인 시트→03→복귀 후
  **수동 재탭**(pending intent 없음, S6 통일; S1 보류재개는 퍼널 CTA 한정). 로딩=
  프로그레시브(히어로 즉시+섹션 스켈레톤, 딥링크 풀 스켈레톤). 상태=fresh/stale 동일·
  stale 무인디케이터, unavailable은 honest-minimal 숨김(소개만 인라인 재시도), 이미지
  전무=무채색 히어로, 404='존재하지 않는 장소'·네트워크=전체화면 재시도, 레일 빈/에러
  조용히 숨김. reconcile: 신규 테이블 없음, nearby 카드에 세분 `lcls_systm3_nm` 라벨
  추가(현 coarse 버킷)·crowd 필드 제거·`info_data`/`moods[]` 본 화면 미사용. 후속:
  detailStatus 매핑·홈페이지 파싱·저장 엔드포인트·API 형식=S9, 외부/딥링크 URL=S8, DB=S7.
- **S7 (2026-06-20) DB 설계(전 화면 종합)** → `S07-db.md`. 현 head=`0010`
  기준(0010이 이미 15테이블·0005가 related_spots/tats 드롭함—재드롭 불필요). 신규=`curations`
  (id bigint·type region|mood|editorial CHECK·slug UNIQUE·title verbatim·cover_spot_id FK SET NULL·
  region_cd/mood_id 풀스코프·is_published·position) + `curation_spots`(curation_id+content_id PK,
  position; canonical contentId라 컬럼명 content_id 통일) + 부분 인덱스 `idx_spots_image_pool
  (ldong_regn_cd) WHERE show_flag=1 AND first_image_url IS NOT NULL`(랜덤 풀 has_kto_image 받침).
  변경=drop column `user_auth_providers.refresh_token_enc`(Redis jti 전용)·`user_consents.
  notification_consent`(알림 비목표); 동의버전=기존 terms_version 유지. 재사용=`users.profile_image_url`
  (avatar는 기존 컬럼·신규 X)+spots/details/images/moods/embeddings/saved 전부 무변경. 드롭 테이블=
  courses·course_days·course_items·notifications·analytics_events·**spot_concentration**(보존→폐기
  재결정 2026-06-20). centroid=**런타임 AVG**(시군구 spots mapx/mapy 평균, 빈 곳=시도 폴백, 신규 컬럼/
  스크립트 없음). 카드 canonical `{contentId,title,firstImageUrl,category}`=spots.* + lcls_systm3→
  lcls_systm_codes.lcls_systm3_nm 조인(세분 라벨), coarse 칩버킷은 별개=S9. 마이그레이션 4리비전
  (autogenerate가 부분/CHECK 인덱스·드롭 downgrade 놓침—수동). 후속: 캐시/딥링크=S8, 직렬화/엔드포인트=
  S9, 마이그↔모듈코드제거 순서=S10.
- **S8 (2026-06-20) 인프라 설계** → `S08-infra.md`. 토폴로지=현행 유지
  (CT112 api+redis+tunnel+runner / CT110 Postgres / CT111 pipeline) + **신규 컴포넌트는 apex
  `pictrip.org`=Cloudflare Pages 하나**(Git 자동배포, 홈서버와 완전 분리; legal 4페이지 무채색 +
  `.well-known/AASA·assetlinks` + `/{spots|curations}/…` 스토어 리다이렉트). **legal=CF Pages 정적**
  (Notion·FastAPI static·앱번들 기각; 구글 OAuth는 기본 scope만이라 소유도메인 검증 무관). **딥링크=
  Universal/App Links**(앱O→화면/앱X→스토어, 공유 URL `https://pictrip.org/{spots|curations}/…`,
  앱스킴 `pictrip://…`, deferred deep link 없음=설치후 홈, Branch류 네이티브 금지; iOS associated
  domains+Android autoVerify intent-filter=엔타이틀먼트라 모듈 아님). **Redis 인증=덴리스트 단일
  모델로 S1 확정**(현 회전+도난탐지 rt:active/deny/grace·sess·user:sessions ZSET·5-key Lua 폐기→
  `denyjti:{jti}` 한 키): 발급시 Redis 0·refresh는 JWT검증+EXISTS만·로그아웃/탈퇴=denyjti SET. 심층
  분석 근거=회전모델은 rt:active가 source-of-truth라 **단일 홈서버서 Redis 소실=전원 강제로그아웃
  (fail-closed)**·도난탐지 순이익 미미·access는 어차피 15분 무검사. 캐시 키=`rlte:`1h·`region:`1d·
  신규 `curation:{id}:spots`(KST자정)·`regions:tree`24h(centroid 런타임 AVG). 영속성=**AOF everysec**
  +RDB, eviction=`noeviction`+`maxmemory 256mb`. **풀 통합**(`redis_cache` 싱글톤은 recommendations
  전용→제거후 고아→단일 lifespan 풀로). CI/CD=현행(backend push-main 자동배포·mobile `v*`→EAS) +
  CF Pages 네이티브 Git연동(워크플로0) + CT112 디스크 prune 주간 systemd timer 룰화. 시크릿=`.env`만
  ·모바일 `EXPO_PUBLIC_*`만·GH는 `EXPO_TOKEN`·Apple은 EAS. 후속: refresh/logout API형식·딥링크 앱
  라우팅=S9, auth.py/풀/compose 구현+마이그↔코드제거 순서=S10.
- **S9 (2026-06-20) API 계약(화면→엔드포인트)** → `S09-api-contract.md`.
  베이스 `/v1`, JSend `{data,error,meta}`(ok/err, traceId 자동), 에러는 `AppError` 코드 분기
  (신규 코드 0, 전부 재사용). canonical 카드 코어 `{contentId,title,firstImageUrl,category}`
  +엔드포인트별 확장(similarity·distance·dist·region/sigunguName·addr/mapx/mapy·overview).
  6모듈 라이브 로스터: **users**(`/auth/oauth/{provider}`·`/auth/refresh`·`/auth/logout`·
  `/users/me`(+DELETE)·신규 `PUT /users/me/consents`{locationConsent:bool,photoConsent?,termsVersion}·
  `/users/me/saved`{**커서+limit**, E3}·saved POST/DELETE) · **taste**(`/taste/photo-search`
  multipart+lat/lng→`{matches[+similarity,distance?,region메타],queryHadLocation}`, 임계~0.60·30·
  0건=빈200) · **spots**(신규 `/home/feed` 히어로6+레일3·신규 `/curations/{slug}`·`/spots/{id}`
  (moods[] 제거)) · **map**(`/map/nearby` radius기본3000·crowd제거·세분라벨·신규 `/map/regions-tree`
  centroid런타임AVG·`/map/region` 유지) · **system**(`/meta/version`·루트 `/health`) · **images**
  (모바일 대면 0). **제거(E1·E4)**: similar·related·moods·moods/{code}/spots·**batch**·평면 regions·
  search·trending·by-region·today-inspo(+recommendations모듈)·courses/*(+courses모듈)·me/notifications·
  analytics/events → 화면 미소비 전부 컷, 소비처 0 검증(역추적표 = 라이브 집합 정확 일치).
  **`/legal`=API 아님(E2)**: 앱 상수 4 {slug,title} + `pictrip.org/legal/{slug}` WebView(호스팅=Cloudflare Pages 정적, S8 확정; Notion 기각).
  `GET /users/me`=`displayName`/`avatarUrl` 직렬화(E5, DB profile_image_url 유지). reconcile→S10:
  OAuth `{provider}`일반화+카카오OIDC, photo-search 재구성, saved 커서, nearby 정리, moods[] 제거,
  리네임, 제거 라우트/모듈 삭제↔Alembic 순서. 후속: 캐시/딥링크=S8, 구현순서=S10.
- **S10 (2026-06-20) Reconcile 종합·마이그·구현순서 — 로드맵 完** →
  `S10-reconcile.md`. S1~S9 reconcile 노트 1개 종합표(DB·auth/Redis·API직렬화·
  신규EP·제거·모바일·인프라)로 통합(하드 모순 0). 척추 원칙=**expand→contract**: `deploy.sh`
  롤백은 이미지만·마이그는 forward-only(롤백된 구 이미지가 새 스키마 위 실행) → 파괴적 마이그는
  무참조 코드가 롤백대상 된 뒤만. **2단계 롤아웃 확정**: Stage A(코드 빌드아웃+제거+auth 덴리스트
  재작성+OAuth `{provider}`+풀통합+신규EP+직렬화+compose, 추가형 M1 curations·M2 image_pool 인덱스
  동반) → 그린·시드 후 Stage B(M3 컬럼드롭 refresh_token_enc·notification_consent + M4 테이블드롭
  courses3·notifications·analytics, `spot_concentration` 보존). 모바일(테마→화면/fetch전환→딥링크
  엔타이틀먼트)·CF Pages(legal 무의존·`.well-known`은 EAS자격 후)=병렬 트랙. 마이그=4리비전 수동
  (부분인덱스 술어·명명 CHECK·드롭 downgrade autogenerate 누락), `_seconds_until_kst_midnight`는
  recommendations 삭제 전 `app/core` 이관. 잔여=`dist`/`distance` 의도된 이중명(버그 아님)·nearby
  세분라벨 직렬화갭·HNSW JOIN 미사용 함정. 검증=단계별 `POSTGRES_DB=pictrip_test`+모바일 스위트+
  시뮬 스모크. **세션 로드맵(S1~S10) 완료.**
- **S11 (2026-06-21) 외부 벤치마크 & 심층분석 개선노트(로드맵 외 보강)** →
  `S11-external-benchmark.md`. 6개 병렬 MCP 리서치(Exa·context7·GitHub)로
  전 설계를 best-practice 대조: 기술 결정 대부분 **검증됨/그 이상**(halfvec·show_flag·URL-only·
  denylist+fail-open·딥링크 토폴로지·서버주도 피드). 추가형 보강(§1~6, 잠긴 결정 강화): CLIP 임계
  0.60 재캘리브+유사도% 버킷표시(과빡빡·오해), 임베딩 36%공백 백필게이트+graceful degradation,
  HNSW ANN-ORDER+LIMIT-then-join 강제, 30일 refresh **슬라이딩**(에코 보정)+공급자별 id_token
  규약(Apple base64url nonce·Google 다중aud·provider+sub키), assetlinks **지문2개**+AASA components+
  웹폴백 Smart App Banner, type↔스코프 **CHECK**, KST자정 일괄만료 **지터**+on-publish 무효화,
  문서정합(동의버전 수명주기·아바타404폴백). **§7 승인 필요(잠긴 결정 뒤집기)**: §7-A `spot_concentration`
  데이터 재융합(트렌딩 화면은 컷 유지, 카드/상세 혼잡도 배지로 — 공모전 "데이터 활용성(20)·융복합"
  유일 약점을 *이미 적재된 6,387행* 자산으로 메움; honest-minimal crowd-제거와 상충 → 사용자 선택),
  §7-B 랜덤채움→품질게이트 랭킹. 컨셉 선례=자칭 Photoplace 등 다수(공식 상위수상 미확인;
  차별=규모+출시완성도). **crosscheck 확정: 1차마감 2026-09-21(사용자 확인)·루브릭 30/30/20/20·
  15128555=공사 집중률 API(재융합이 공사 OpenAPI 게이트 충족)·S4 유사도%항상노출·auth 30일고정에코.**
- **A1+ (2026-06-21) 어드민 홈 큐레이션 편집기 채택 (스코프 확장, read-write)** →
  `admin/A01-admin-console.md`(A9·§7·Phase 4), 목업 `mockups/admin/curation.html`(B안 확정),
  요구사항 `requirements/dev-requirements.md`(ADM-012~018). A01 본래 "콘텐츠 큐레이션=비목표·
  어드민 read-only" 결정을 **사용자 승인으로 뒤집음**: 홈 편성(히어로6+무드레일3)을 앱 재배포
  없이 운영자가 편집/발행(홈=백엔드 주도 잠긴 결정 2의 마지막 조각; 현재는 시드 스크립트 수정이
  유일 경로). 어드민에 **`curations`/`curation_spots` 한정 스코프된 쓰기** 도입(그 외 표면 read-only
  유지). 신규 admin API(목록·상세·편집·손픽·스팟검색) + 발행 시 BE-HOME-003 캐시 무효화 재사용 +
  변경 audit. 표지=KTO URL 참조만(다운로드 금지). 회원 관리는 여전히 비목표.

## 교차 reconcile 결정 (2026-06-20 심층분석 + 독립 에이전트 패널)

전 스펙을 목업과 대조 + 3렌즈 패널(목업충실/이상UX/구현현실) 종합 → 화면 스펙에 일괄 반영:

- **A1 권한 04 살림**: 지도 진입 시 미결정→04① priming/거부→04② denied, "나중에/둘러보기"→
  서울중심 degraded. S5 발명 GPS 배너 제거. 사진흐름은 04 미트리거(S4). (S1·S5 정정)
- **A2 마이 게스트**: 마이 탭은 게스트 열람 가능(15b). 풀스크린 로그인은 마이 내부 로그인
  행/버튼 탭 시에만(탭 진입 자체로 강제 안 함). S1의 "마이 탭=로그인 필요" 폐기. (S1 정정)
- **A3 사진=런처**: 4탭 중 사진은 탭 화면이 아니라 모달 스택(08→09→10→07) 런처. 셸 소유=S1 §5.1.
- **C1 카드 DTO 통일(백엔드 ground truth로 검증)**: canonical `{contentId, title, firstImageUrl,
  category}`(camelCase+KTO명). S2 `{spot_id,name,image_url}`·S4/S6 `{spotId,thumbnailUrl}` 폐기.
  저장 경로 `/users/me/saved/{contentId}`·프로필 `/users/me`(S6 `/me/saved-spots/{spotId}` 폐기).
  백엔드/모바일/S3·S5와 이미 일치. (S2·S4·S6 정정)
- **C2 거리 단일 util** `formatDistance(m)`: <1km `{정수}m` / 1–10km `소수1 km` / ≥10km `정수 km`.
  S4·S5 동일 함수, 서버는 dist(m) 반환. (S4·S5 정정)
- **B1 레일 ≤8 가변**(목업 3 노출+가로 스크롤; "정확히 8" 폐기). (S2 정정)
- **B5 카드 라벨=세분 subtype(`lcls_systm3_nm`)** / 칩 필터=6 coarse 버킷. nearby 응답에 세분
  라벨 추가(S3 §7과 동일 reconcile). (S2·S5 정정)
- **B2 발명 surface 라벨링**: 빈/에러/로딩·로그인 시트는 "목업 happy-path 외 설계 추가"로 명시
  (verbatim 아님). 권한·로그인 기본 표면=목업 풀스크린(시트는 파생). (S1·S4 정정)
- **B4 지역피커**: 17 시도(목업 12=트렁케이션), `{시도}전체`=탭 가능 선택 행. (S5 명시)
- **B6**: 06 상세 응답 `subtitle` 생략(목업 무), 로그인 태그라인 드롭(목업 빈 슬롯). (S1·S2 정정)
- **B3 카피 등록**: 온보딩 서브캡션 3종(S1)·히어로 6 카피(S2) 목업 verbatim 레지스트리화.
- **C3 셸 소유=S1 §5.1**(4탭·모달규칙·사진 런처).
- **D1 이모지 제거**(S6 house 이모지→홈 라인-SVG), **D2 홈 푸터 "문의" 제거**(목업 05+S2; 목적지 없는 고아).
