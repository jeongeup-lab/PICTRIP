# Mobile P4 — 지도(내 주변) + 권한 04 + 지역 선택 12 설계

> 2026-06-22 brainstorming 세션. 입력: `docs/mockups/04-permissions.html`·`11-map.html`·
> `12-region-picker.html`(UI SSOT), `docs/specs/screens/S05-map-region.md`(잠긴 결정),
> `docs/specs/screens/S01-onboarding-auth.md` §4·§5.1(권한 04 트리거·셸), 백엔드 `app/modules/map/`
> (계약), P0–P3 코드(패턴). 산출물 = 화면/네비/모듈 설계. 구현 플랜은 writing-plans로 분리.

## 0. 목표 한 줄

4-탭 셸의 **지도 탭**을 완성한다: 현위치(또는 선택 지역) 반경 3km의 KTO 스팟을
KakaoWebMap 핀 + 3-스냅 바텀시트 리스트로 탐색하고, GPS 미허용 시 권한 04로 안내하며,
헤더 라벨에서 17 시도→시군구 지역 피커로 중심을 점프시킨다. 게스트도 권한 없이 사용 가능.

---

## 1. 범위 & 경계

### 1.1 P4 포함
- **11 지도**: KakaoWebMap(WebView + Kakao JS SDK) + 스팟 핀 + 현위치 마커.
- **3-스냅 바텀시트**(peek ~12% / half ~58% 기본 / full ~92%) + 단일선택 카테고리 칩 + 거리순 리스트(30 상한).
- **"이 지역에서 검색" pill**(패닝 임계 초과 시) + **리센터 FAB**.
- **04 권한**: priming(미결정) / denied(거부) — 지도 진입·리센터 트리거.
- **12 지역 피커 모달**: 17 시도 → 시군구 2단, `검색` CTA 명시 적용.
- **헤더 라벨**: anchorSource별 접두사 규칙(현위치 vs 지역명).

### 1.2 P4 제외 (→ P5)
- 16 법적고지. (P4는 지도/권한/지역만.)

### 1.3 확정 보조 결정 (2026-06-22 승인)
- **바텀시트 = 순수 RN `Animated` + `PanResponder`**(새 네이티브 모듈 0). S05 스펙의
  "gesture-handler/reanimated" 문구는 CLAUDE.md "새 네이티브 모듈 금지" 제약으로 **재정의**.
- **Kakao JS 앱키 = `EXPO_PUBLIC_KAKAO_JS_KEY` 플레이스홀더 + graceful degrade**: 키 없으면
  지도 영역은 blank inset placeholder, 리스트/권한/피커는 정상. 콘솔 셋업은 §9 체크리스트.
- **권한 04 = 지도 탭 내 풀스크린 오버레이 컴포넌트**(별도 라우트 아님). 지도가 유일 트리거.
- **범위 = 단일 스펙/플랜**(04+11+12). SDD 태스크로 세분.

---

## 2. 아키텍처 — `features/map/` 신규 모듈

기존 레이어 규약 준수(`features/<domain>/{api,queries,stores,usecases,lib,components}`).
파일명: 컴포넌트 PascalCase, 런타임 모듈 kebab-case, `src/app/**` Expo Router.

```
src/features/map/
  api.ts        getNearby(lat,lng,category?)→NearbySpot[] · getRegionLabel(lat,lng)→RegionLabel · getRegionsTree()→RegionNode[]
  queries.ts    useNearbyMap(center,category) · useRegionLabel(center,anchorSource) · useRegionsTree()
  stores/map-store.ts   zustand 단일 진실원(아래 §3)
  usecases/request-location.ts  ensureLocation(): 권한 요청 + getCurrentPositionAsync → { status, coords? }
  lib/nearby-categories.ts  CHIPS: [전체|관광지|음식점|카페|레저|쇼핑] ↔ category 파라미터
  lib/region-label.ts       formatHeaderLabel(anchorSource, regionLabel) → 표시 문자열
  lib/kakao-map-html.ts      buildKakaoMapHtml(jsKey): string  (SDK autoload=false + 브리지 JS)
  lib/search-here.ts         shouldShowSearchHere(viewport, lastQuery, radius): boolean (haversine > 임계)
  lib/geo.ts                 haversineMeters(a, b)  (search-here/임계 공용 순수 함수)
  components/KakaoWebMap.tsx     WebView 양방향 브리지 (jsKey 빈값 → blank placeholder)
  components/MapBottomSheet.tsx  Animated+PanResponder 3-snap (공유 Animated.Value)
  components/CategoryChips.tsx · NearbyCard.tsx · SearchHerePill.tsx · RecenterFab.tsx
  components/PermissionPrimer.tsx  04 오버레이 (variant: "priming" | "denied")
  components/RegionPicker.tsx      12 모달 (dim + 2-pane + 검색 CTA)
src/constants/env.ts   (+ KAKAO_JS_KEY)
src/constants/map.ts   SEOUL_CITY_HALL = { lat: 37.5666, lng: 126.9784 }, RADIUS_M = 3000, NEARBY_CAP = 30, SEARCH_HERE_RATIO = 0.3
mobile/.env.example    (+ EXPO_PUBLIC_KAKAO_JS_KEY=)
src/app/(tabs)/map.tsx ComingSoon 대체 — 전체 오케스트레이션
```

기존 자산 재사용: `NearbySpot`(api-types, dist/regionName/sigunguName/overview/congestion 포함),
`formatDistance`(lib/distance), `RemoteImage`, `Skeleton`, `Icon`(map-pin/location/recenter/search/
chevron 등 보유), 테마 토큰. `react-native-webview`·`expo-location`은 기설치.

> **note**: 스팟 상세의 NearbyRail이 쓰는 `features/spots/api.ts#getNearby`(limit 12)는 그대로 둔다.
> 지도는 category 파라미터 + 30 상한이 필요하므로 `features/map/api.ts`에 별도 호출을 둔다.

---

## 3. map-store (단일 진실원)

zustand. `useAuthStore`/`photo-flow-store` 패턴(`getState()` 테스트 가능).

상태:
```
center: { lat, lng } | null        // 현재 조회 중심
anchorSource: "gps" | "region" | "pan"
category: NearbyCategory | null     // null = 전체
gpsCoords: { lat, lng } | null      // 현위치 마커 + 리센터용 (degraded면 null)
label: RegionLabel | null           // 헤더 라벨 데이터
snap: "peek" | "half" | "full"      // 진입 기본 half
viewportCenter: { lat, lng } | null // 패닝 중 마지막 맵 중심(조회 안 함)
lastQueryCenter: { lat, lng } | null// 마지막 /map/nearby 중심 (pill 임계 기준)
selectedSpotId: string | null       // 핀↔카드 연동
```
액션: `setAnchor(center, source, gps?)` · `setCategory(c)` · `onViewportChange(c)`(pill 계산) ·
`searchHere()`(viewport→center, source=pan) · `recenterToGps()` · `applyRegion(centroid)`(source=region) ·
`setSnap(s)` · `selectSpot(id)` · `reset()`. pill 표시는 `shouldShowSearchHere(viewport,lastQueryCenter,RADIUS_M)` 파생.

### 진입/전이
- **진입**: `ensureLocation()` → `granted`: center=gps, source=gps, gpsCoords=set → nearby+label 조회 /
  `undetermined`: `PermissionPrimer priming` / `denied`: `PermissionPrimer denied`.
  "나중에/둘러보기" → center=SEOUL_CITY_HALL, source=pan, gpsCoords=null(현위치 마커 없음), label="서울 중구"(접두사 없음).
- **칩 변경**: center 유지, category만 교체 재조회.
- **패닝(맵 dragend)**: `onViewportChange` — 조회·라벨·핀 변화 없음. viewport가 lastQueryCenter에서 임계(반경 30%) 초과 → pill 등장.
- **"이 지역에서 검색"**: center=viewport, source=pan → 재조회, label=역지오코딩(접두사 제거), pill 숨김.
- **리센터 FAB**: gpsCoords 있으면 center=gps,source=gps 재조회+라벨 복귀; 없으면 `ensureLocation()` 재실행(권한 04 재진입).
- **헤더 라벨 탭**: RegionPicker 오픈. 검색 CTA → `applyRegion(centroid)`(source=region), 라벨=지역명, 재조회, 닫기.
- **핀 탭**: `selectSpot(id)` → snap=half + 카드 스크롤/하이라이트. **카드 탭**: `/spots/[contentId]`.

---

## 4. KakaoWebMap 브리지

`buildKakaoMapHtml(jsKey)` → HTML 문자열:
- `<script src="//dapi.kakao.com/v2/maps/sdk.js?appkey={jsKey}&autoload=false">` + `kakao.maps.load(() => …)` 맵 생성.
- **RN→WebView**(`webviewRef.injectJavaScript`): `setCenter(lat,lng)` · `setPins(spots)` · `setUserMarker(lat,lng|null)` · `recenter()`.
- **WebView→RN**(`window.ReactNativeWebView.postMessage`): `ready` · `pin_tap:{contentId}` · `center_changed:{lat,lng}`(dragend/idle).

`KakaoWebMap.tsx` props: `center` · `pins: NearbySpot[]` · `userLocation` · `onReady` · `onPinTap(id)` · `onCenterChanged(c)`.
핀=잉크 물방울+흰 테두리, 현위치=파란점(`#2D7DF6`)+halo(기능 마커 — 무채색 예외). **jsKey 빈값이면 WebView 대신 blank inset placeholder 렌더**(degrade; 리스트/권한/피커 정상).

---

## 5. 상태 / 에러 (S05 §1.5)

| 상태 | 지도 | 시트 |
|---|---|---|
| loading | 이전 핀 유지 | 스켈레톤 카드 3~4 |
| normal | 핀 N + (조건부)현위치 마커 | 거리순 카드 |
| empty(0건) | 핀 없음, 현위치 마커만 | "이 주변엔 아직 추천 스팟이 없어요" + "지도를 옮겨 '이 지역에서 검색'을 누르거나, 다른 지역을 선택해 보세요" |
| GPS 거부→둘러보기 | 서울 중심, 현위치 마커 없음 | 정상 리스트(배너 없음) |
| error | 이전 상태 유지 | "주변 정보를 불러오지 못했어요" + "다시 시도"(동일 파라미터) |

empty vs error = 빈배열(2xx) vs AppError. error만 재시도, empty는 위치 변경 유도.
RegionPicker tree fetch 실패 = 시트 내 "지역 목록을 불러오지 못했어요" + 다시 시도.

NearbyCard: 큰 사진(firstImageUrl, KTO URL 다운로드 금지) / 인셋 폴백 · title · 메타(map-pin +
`{동}·{세분 category}·{거리=formatDistance(dist)}`) · overview 첫 줄(verbatim, null이면 생략) ·
혼잡도 칩(congestion: 한산/보통/붐빔, null이면 숨김 — 무채색 텍스트 칩).

---

## 6. 규약 준수 (CLAUDE.md)

- **무채색 토큰만**. 예외 = 현위치 마커 파란점(`#2D7DF6`, 기능 마커, S05 §1.2 명시). 혼잡도=무채색 텍스트 칩.
- **이모지 금지** → line-SVG `<Icon>`.
- **`as any` 금지** → `as unknown as T`.
- **JSend 1회 언래핑**: 새 `api.ts`는 재언래핑 금지. `err.code` 분기.
- **지도 = KakaoWebMap(WebView + JS SDK)**, `@react-native-kakao/map` 금지.
- **새 네이티브 모듈 0**: 바텀시트 Animated+PanResponder, webview/expo-location 기설치.
- **시크릿**: `EXPO_PUBLIC_KAKAO_JS_KEY` env만, 코드/커밋에 키 미포함.
- **권한 프롬프트**: 지도는 진입 시 `requestForegroundPermissionsAsync` 호출 OK(사진검색과 달리 위치가 핵심).

---

## 7. 테스트 전략

순수 로직 TDD(jest + 목, P2/P3 패턴):
- `nearby-categories`(칩↔파라미터 매핑, 전체=undefined)
- `region-label`(gps→"현위치 · {동}" / region·pan→"{지역명}" 접두사 없음)
- `geo.haversineMeters` + `search-here.shouldShowSearchHere`(임계 경계)
- `kakao-map-html`(키 주입, autoload=false, SDK url 포함)
- `map-store`(getState 전이: setAnchor/setCategory/onViewportChange→pill/searchHere/recenter/applyRegion)
- `request-location`(expo-location 목: granted/denied/undetermined 매핑, 좌표 반환)
- `map/api`(호출 형태: category 파라미터, regions-tree)

화면/오버레이/WebView/시트(`KakaoWebMap`·`MapBottomSheet`·`RegionPicker`·`PermissionPrimer`·`(tabs)/map.tsx`)
= 단위 미테스트 → lint + typecheck + format:check + 전체 suite green + 수동 스모크 체크리스트.

검증(매 태스크): `cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test`.
커밋 태스크별, 푸시는 요청 시에만.

---

## 8. 신규 의존성

**없음**(전부 기존: react-native-webview, expo-location, Animated/PanResponder).

---

## 9. 콘솔 셋업 체크리스트 (실 지도 — 별도 작업)

> P4 코드는 플레이스홀더로 동작(키 없으면 지도 blank, 나머지 정상). 실 지도는 아래 후 `.env` 주입.

- **Kakao Developers** 앱 → **JavaScript 키** 발급 → `.env` `EXPO_PUBLIC_KAKAO_JS_KEY`.
- 플랫폼 설정 → **Web 플랫폼 도메인 등록**(WebView 로드 origin; Expo dev는 적절한 허용 origin/about:blank 고려).
- `/map/nearby`·`/map/region`(Kakao coord2regioncode)·`/map/regions-tree`는 백엔드 기구현(키는 서버 측 REST).

---

## 10. 미해결 / 이월

- 반경 3km·"이 지역에서 검색" 임계(반경 30%)는 실데이터 밀도로 구현 후 체감 조정(S05 §5).
- 실 지도 렌더 end-to-end 수동 스모크는 실 JS 키 확보 후(§9). Expo Go vs dev client에서 WebView+Kakao SDK 로드 동작 확인 필요.
- `category` 파라미터 값은 백엔드 `NearbyCategory` enum과 1:1 일치해야 함 — 플랜 Task에서 enum 실값 확인.
