# PicTrip 리팩토링 — 설계 브리프 (시드)

> 이 문서는 **새 세션에서 기능 명세서/설계를 작성하기 위한 출발점**입니다.
> 스펙 본문이 아니라 스코프·제약·구조를 잡아두는 시드입니다. 새 세션은
> `brainstorming` 스킬로 시작해 이 브리프를 입력으로 쓰고, 결과 스펙을
> `docs/specs/`에 작성합니다.

## 목표

`docs/mockups/`(무채색 16화면)를 기준으로 PicTrip을 리팩토링한다. 구현에
끌려가지 않도록 **설계를 먼저 완전히 끝낸다**: 화면별 + 인프라 + DB 설계.

## 설계 원칙 — "구현이 없다고 가정"

- 화면/UX/네비게이션/API **형태**는 백지에서 이상적으로 설계한다(기존 코드에
  맞추지 않는다).
- **단, DB·인프라는 "이상 설계 → 현실 reconcile"**다. 아래 자산/제약은 가정으로
  지울 수 없다. 마지막에 reconcile 섹션으로 차이를 명시한다.

### 지울 수 없는 자산 / 제약 (reconcile 대상)

- 프로덕션 DB에 **spots ~68k + CLIP 임베딩 ~64%**(KTO 출처) 적재됨 — 새 스키마를
  깨끗이 그리되 이 자산을 버리지 말고 매핑/마이그레이션 경로를 잡는다.
- **KTO 컴플라이언스**: 이미지 다운로드/저장 금지(URL만), `overview` verbatim,
  임베딩 컬럼 `halfvec(512)`.
- **인프라**: Proxmox 홈서버(FastAPI+Redis CT112, Postgres CT110), Cloudflare
  터널 `https://api.pictrip.org`, GitHub Actions + self-hosted runner. **No AWS.**
- **모바일 네이티브**: 지도는 KakaoWebMap(WebView+JS SDK), `@react-native-kakao/map`
  뷰 금지. Expo SDK 56 네이티브 핀(gesture-handler/reanimated) 고정. 새 네이티브
  모듈 추가 금지.
- 토큰: access=메모리, refresh=expo-secure-store.

## 스코프

### 1. 화면 (목업 16개)

| # | 목업 파일 | 화면 |
|---|---|---|
| 01 | `01-splash.html` | 스플래시 |
| 02 | `02-onboarding.html` | 온보딩 |
| 03 | `03-login.html` | 로그인 |
| 04 | `04-permissions.html` | 권한 |
| 05 | `05-home.html` | 홈 (큐레이션 피드) |
| 06 | `06-curation.html` | 큐레이션 상세 |
| 07 | `07-spot.html` | 스팟 상세 |
| 08 | `08-photo-select.html` | 사진 선택 |
| 09 | `09-analyzing.html` | 분석 중 |
| 10 | `10-result.html` | 사진 검색 결과 |
| 11 | `11-map.html` | 지도(내 주변) |
| 12 | `12-region-picker.html` | 지역 선택 |
| 13 | `13-saved.html` | 저장(스크랩) |
| 14 | `14-profile.html` | 프로필 |
| 15 | `15-profile-states.html` | 프로필 상태들 |
| 16 | `16-legal.html` | 약관/법적고지 |

화면별로 명세할 것: 목적 · 구성요소 · 상태(loading/normal/empty/error) ·
데이터 needs · 진입/이탈 네비게이션 · 인터랙션 · 빈/에러 구분.

### 2. 데이터 / DB 설계

엔티티 · 관계 · 핵심 컬럼 · 인덱스. KTO 소스 스키마와 reconcile(현재:
`spots`/`spot_details`/`spot_images`/`spot_moods`/`moods`/`regions`/`sigungus`/
`lcls_systm_codes`/`spot_embeddings`/`users`/`user_auth_providers`/
`user_consents`/`user_saved_spots`).

### 3. 인프라 설계

배포 토폴로지 · 서비스 구성 · CI/CD. 현 홈서버 토폴로지 기준.

### 4. API 계약

화면 인터랙션 → 엔드포인트. JSend 엔벨로프 `{ data, error, meta }`,
`AppError` 코드 분기.

## 비목표 / 제거 결정 (이미 확정)

이번 제품에 없는 기능 — 설계에 넣지 않는다:

- **코스(course)** 기능 일체
- **텍스트 검색**(`/spots/search`) · **트렌딩**(`/spots/trending`)
- **today-inspo** 추천
- **알림**(`/me/notifications`) · **analytics 이벤트**
- 백엔드 모듈은 6개로: users · taste · spots · images · map · system
- 유지: images/`spot_embeddings`(photo-search + similar 지탱)

## 산출물

`docs/specs/`에 기능 명세서 + 설계 문서. 마지막에 **reconcile 노트**(이상 설계
vs 현 자산/제약, 마이그레이션 방향).

## 입력 포인터

- 디자인 SSOT: `docs/mockups/` (`index.html` 갤러리)
- 아키텍처/제약 SSOT: `CLAUDE.md` (루트, 127줄)
- 결정 이력: 메모리 `mockup_refactor_plan`
