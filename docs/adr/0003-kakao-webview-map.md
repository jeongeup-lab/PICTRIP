# 0003. 지도는 KakaoWebMap (WebView + JS SDK)

- 상태: 채택
- 날짜: 2026-06-11
- 관련: `mobile/src/features/map/components/KakaoWebMap.tsx`

## 맥락
`@react-native-kakao/map` 네이티브 뷰는 Android가 미구현이고 iOS 시뮬레이터에서
빈 화면만 렌더된다. 새 네이티브 모듈은 Expo SDK 56 핀 트리를 깨뜨린다
(expo-modules-core pod 충돌).

## 결정
**지도는 WebView에 Kakao JS SDK를 얹은 `KakaoWebMap` 단일 구현으로 간다.**
네이티브 카카오맵 뷰로 되돌리지 않는다. SDK는 동적 로드하고 `onerror`에서
fetch 재프로브로 HTTP 상태를 RN 오버레이에 노출한다 — 동기 `<script src>`는
도메인 거부/네트워크 실패 시 조용히 죽어 지도만 빈 화면이 된다. bbox 보고는
`idle` 이벤트를 쓴다 — 드래그·줌뿐 아니라 프로그래매틱 `setCenter` 후에도
발화해야 "이 지역에서 검색"이 모든 이동을 본다.

## 고려한 대안
- **네이티브 카카오맵 뷰** — Android 미구현·iOS 시뮬 blank. 기각.
- **다른 지도 공급자** — 국내 POI 품질·카카오 딥링크 연계에서 열위. 기각.

## 결과
- 시뮬레이터·에뮬레이터에서 동작한다 (시뮬 GPS는 `simctl location set` 필요).
- 지도 성능 한계(회전 미지원 등)는 JS SDK 제약으로 수용한다.
