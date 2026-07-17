# 결정 로그

> 갱신: 2026-07-17 · **append-only** — 새 결정은 맨 위에 추가한다. 결정을 뒤집으면
> 지우지 말고 새 항목으로 기록한다. 상세 설계 히스토리(구 `docs/specs/` S00–S13
> 스펙·`docs/plans/`)는 git 히스토리에 보존되어 있다.

## 현행 원칙 (요약)

| 영역 | 원칙 |
|---|---|
| 제품 | 홈 = 해외 사진 피드 → 스와이프 시 닮은 국내 관광지 3곳 매칭 (LLM 미사용, CLIP 임베딩) |
| 데이터 | 소스는 KTO OpenAPI 호출만 (파일데이터 다운로드는 공모전 불인정) |
| 이미지 | 공공누리 경계 — Type1 변형 가능 · Type3 원본 무변형 · 출처표시 유지; 사용자 업로드는 미영속 |
| 인증 | denylist-only (`denyjti:{jti}`, fail-open) — 세션/디바이스 테이블·refresh 회전 없음 |
| DB | 마이그레이션은 expand→contract, forward-only (배포 롤백은 이미지만) |
| 디자인 | SSOT = 구현된 앱(`mobile/src`); 목업은 일회성 핸드오프 후 폐기 |
| 문서 | 현행만 기록, 히스토리는 이 로그 + git; 코드로 알 수 있는 것은 쓰지 않는다 |

## 로그 (최신순)

- **2026-07-17 · 문서 재구조화** — 스펙 16·플랜 7·목업 전체를 삭제하고 현행 문서
  4종(product·architecture·operations·decisions)으로 대체. 문서는 코드가 말하지
  못하는 "무엇·왜·운영"만 담는다.
- **2026-07-17 · KTO 재시도 = transient-only** — 429·5xx·타임아웃/네트워크 단절만
  재시도(backend·pipeline 동일). 4xx 재시도는 일일 쿼터만 소진.
- **2026-07-17 · `/v1` compat shim 제거** — v0.4.1 구제용 임시 미들웨어. 72h 프로드
  로그에서 대상 트래픽 0건 확인 후 제거.
- **2026-07-17 · Curation ORM 제거, 테이블 보존** — `curations`/`curation_spots`는
  참조 0건이라 모델 삭제, 테이블은 Alembic autogenerate `include_object` 제외로 보존.
- **2026-07-17 · 매칭 품질 P0+P1** — 매칭 후보를 attraction 버킷으로 게이트, 현대
  도시·온천마을 해외행 제외/숨김(77건), 갤러리(다중 이미지) centroid 임베딩으로 대표사진
  복권 완화 + 일일 백필 크론(KTO 쿼터 내 800스팟/일).
- **2026-07-16 · KTO 이미지 정책 재정의** — 운영사무국 확인으로 구 "다운로드·재호스팅
  금지" 폐기(해당 조항은 콘텐츠랩 파일데이터 규정 혼동). 프록시/CDN 캐싱 허용, 경계는
  공공누리 `cpyrhtDivCd`(Type1 변형 가능 · Type3 무변형 pass-through만).
- **2026-07-16 · 이미지 화질 체인** — 매칭·채널 이미지는 `img.pictrip.org` t1 서명
  변환(폭 1620 무손실 원칙, 타일 320) + 일일 캐시 워밍. 발급 SSOT =
  `backend/app/modules/feed/services/display.py`.
- **2026-07-15 · 이미지 렌더 2단계** — blur-up 프리뷰(OTA) + expo-image
  memory-disk 캐시(v0.6.0 네이티브).
- **2026-07-12 · S13 구현 확정치** — `MATCH_DISTANCE_MAX=0.32`, 해외 스팟 2,347행
  (Wikidata ETL), 임베딩 100%, 매칭 캐시 `match:{revision}:{overseasId}` TTL 6h.
- **2026-07-11 · 유사도 % = 정직 버킷** — 코사인 거리를 과장 없는 버킷 문구로 표시
  (마케팅성 % 부풀림 금지).
- **2026-07 · S13 홈/탐색 재설계** — 구 "큐레이션 홈 + 사진 업로드 검색"(잠긴 결정
  1·2·3)을 폐기하고 해외 피드→국내 매칭으로 전환. `taste` 모듈·`/home/feed`·
  `/curations/{slug}` 제거, `/feed`·`/overseas/{id}/matches`·`/home/channels`
  (hot·hidden·festa·snap·pets) 신설. 모듈 구성 = users·spots·feed·images·map·
  system·admin. 구 큐레이션 공유 링크는 `web/_redirects` `/curations/* → /` 302로 착지.
- **2026-07-08 · 어드민 하드닝(CH1·CH2)** — 발행 토글·congestion 카드 필드 철회.
  대부분 S13으로 은퇴했으나 `spot_concentration` 자산 보존 결정은 유지되어 현
  Hot/Hidden 채널의 소스가 됨.
- **2026-06-28 · 카카오 로그인 = https 바운스** — 커스텀 스킴 거부로
  `web/oauthredirect → pictrip://` 웹 바운스 사용, OIDC ON·클라이언트 시크릿 OFF.
- **2026-06-27 · 어드민 인증 = DB-backed** — `admin_users` 테이블(bcrypt), env 아님.
  프로비저닝/로테이션은 CT110 DB 쓰기만으로 가능(`scripts/set_admin_password.py`).
- **2026-06-27 · cloudflared = CT112 호스트 프로세스가 SSOT** — compose 내 서비스
  아님(`/etc/cloudflared/config.yml`).
- **2026-06-23 · 배포 레일 확정** — dev 머지 = 자동 배포(스테이징 없음), main =
  릴리스 마커, `v*` 태그 = TestFlight 네이티브 빌드, dev push = EAS OTA(JS만).
- **2026-06-21 · 어드민 콘솔 스코프** — read-only 교차 모듈 집계 +
  `overseas_spots.is_hidden` 한정 쓰기만(회원 관리 비목표). 큐레이션 편집기는
  이후 S13으로 은퇴.
- **2026-06-20 · 인증 = denylist-only** — refresh 회전+도난탐지 모델 기각: 단일
  홈서버에서 Redis 소실 시 회전 모델은 전원 강제 로그아웃(fail-closed)이라
  `denyjti:{jti}` 단일 키 + fail-open 채택. access=메모리 15분, refresh=secure-store 30일.
- **2026-06-20 · 마이그레이션 = expand→contract** — `deploy.sh` 롤백은 이미지만이므로
  마이그는 forward-only, 파괴적 변경은 무참조 코드가 롤백 대상이 된 뒤에만.
- **2026-06-20 · 딥링크 = Universal/App Links** — 공유 URL `https://pictrip.org/spots/…`
  + 앱 스킴 `pictrip://`, deferred deep link 없음(설치 후 홈), Branch류 네이티브 금지.
  legal 4문서 = CF Pages 정적(`pictrip.org/legal/{slug}`) + 인앱 WebView.
- **2026-06-20 · 카드 DTO canonical** — `{contentId, title, firstImageUrl, category}`
  (camelCase, KTO 필드명 유래) + 엔드포인트별 확장. 거리 표기는 단일
  `formatDistance(m)`: <1km `{정수}m` / 1–10km 소수1 km / ≥10km 정수 km.
- **2026-06-20 · 시군구 centroid = 런타임 AVG** — spots mapx/mapy 평균, 사전계산
  컬럼/스크립트 없음.
- **2026-06-14 · 4탭 셸 확정** — 홈·탐색·지도·마이 + 저장→스크랩(마이 흡수),
  코스·알림 모바일 제거.
- **2026-06-13 · 텍스트 검색 은퇴** — 홈에서 검색 진입점 제거, 관련 코드 삭제.
- **2026-06-11 · 지도 = KakaoWebMap** — WebView + Kakao JS SDK.
  `@react-native-kakao/map` 네이티브 뷰 금지(Android 미구현·iOS 시뮬 blank).
- **상시 제약** — Expo SDK 56 네이티브 핀 고정(새 네이티브 모듈 금지, dependabot
  범프 거부), No AWS(Proxmox 홈서버 + Cloudflare), 비목표 = 코스·텍스트검색·
  트렌딩 화면·알림·analytics.
