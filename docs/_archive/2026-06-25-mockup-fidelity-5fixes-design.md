# Design — Mockup-fidelity pass: 5 fixes

Date: 2026-06-25 · Author: autonomous session (Opus 4.8)
Scope: `mobile/` (+ `mobile/eas.json`, `mobile/.env`). No backend code change expected.

## Goal

Bring five mobile surfaces to 100% fidelity with `docs/mockups/` (the design SSOT)
and make the Kakao map actually render. The user enumerated:

1. Splash screen does not appear (`01-splash.html`).
2. Onboarding must match `02-onboarding.html` exactly.
3. Spot detail must match `07-spot.html` exactly.
4. Region picker must match `12-region-picker.html` (left 33% / right flex) **and**
   list every 시군구 nationwide (currently left column too wide, district list sparse).
5. Kakao map does not render — fix with `pictrip-legacy` as reference.

## Current state (verified)

- **Splash**: `src/app/index.tsx` (`BootGate`) shows a bare `ActivityIndicator` on a
  white screen while hydrating auth + onboarding flag. No styled splash. `app.json`
  has no `splash` config (white native flash).
- **Onboarding**: `src/app/onboarding.tsx` — 3 text-only slides + dots + CTA. No STEP
  eyebrow, no mini-device previews, no 건너뛰기 skip.
- **Spot detail**: `src/app/spots/[contentId].tsx` + `src/features/spots/components/*`
  (IntroSection, Gallery, LocationSection, NearbyRail). Missing: gallery strip inside
  hero, "전체 사진" glass button, map block + 네이버/카카오 links, info rows with icons,
  "방문 예정" inset (공유/스크랩), title "주변 둘러보기".
- **Region picker**: `src/features/map/components/RegionPicker.tsx` — left `34%`, rows
  too tight/small vs mockup; data from backend `GET /map/regions-tree`, whose `sigungus`
  table is pipeline-seeded and sparse in prod → not all districts appear.
- **Kakao map**: `src/features/map/components/KakaoWebMap.tsx` +
  `src/features/map/lib/kakao-map-html.ts`. Root causes: (a) no local `.env` so
  `KAKAO_JS_KEY=""` → placeholder in the simulator; (b) WebView `source` lacks
  `baseUrl: 'https://localhost'`, which the Kakao JS SDK domain check requires
  (legacy pins exactly this origin). `eas.json` already injects a JS key for builds;
  `app.json` already has `eas.projectId`.

## Decisions

- **Splash**: render the mockup splash inside `BootGate` (dark `#000` bg, centered
  line-SVG selfie figure + `PicTrip` wordmark, white status text area), replacing the
  ActivityIndicator. Also set `app.json` `splash` (backgroundColor `#000`, `resizeMode
  contain`) so there is no white native flash before JS mounts. Use a generated
  selfie SVG matching `01-splash.html` paths via the existing `react-native-svg`
  stack — no new native module, no bitmap asset required for the JS splash. (Native
  splash needs a PNG; generate a minimal 1024² dark PNG with the wordmark, or set
  backgroundColor only if PNG generation is unavailable.)
- **Onboarding**: rebuild `onboarding.tsx` to match `02-onboarding.html`: paged
  horizontal `ScrollView`, per-slide STEP eyebrow + caption, a scaled mini-device
  preview (fixed-size inner View with `transform:[{scale}]` ~0.6 of a 392-wide design
  frame) reproducing the photo select / analyzing / result screens, 건너뛰기 skip
  (top-right), animated dots (active = wide pill), CTA "사진으로 시작하기". Skip and CTA
  both finish onboarding → `/(tabs)`.
- **Spot detail**: rebuild the screen + section components to match `07-spot.html`
  exactly: hero (scrim, back + 스크랩 buttons, title, subline `category · region`,
  description) → gallery strip (300/108 tiles) → "전체 사진" glass button →
  소개 (overview + 더보기) → 위치 (map preview + 네이버 지도 / 카카오 지도 deep-link
  buttons + info rows: address / hours / phone / website, each with its icon) →
  방문 예정 inset (공유 / 스크랩 cards) → 주변 둘러보기 rail (150×112 cards). Wire to the
  existing `SpotDetail` query shape; deep links from `mapx/mapy`/title.
- **Region picker**: bundle a complete static region tree
  `src/constants/regions.ts` — all 17 시도, every 시군구, each with an approximate
  centroid `{lat,lng}` (district office coords; only used to recenter the map).
  `RegionPicker` reads this static tree (drops the backend dependency for the list),
  guaranteeing completeness. Re-style to the mockup: left column `33%`, right column
  flex; row paddings ~19px (left) / ~18px (right); inactive 17/16px `ter`, active
  18px `800` `ink`; "{시도} 전체" header row; CTA 56px "검색". `onApply(centroid, label)`
  contract unchanged.
- **Kakao map**: minimal, legacy-aligned fix to `KakaoWebMap.tsx` /
  `kakao-map-html.ts`: add `baseUrl: 'https://localhost'` to the WebView `source`;
  add an `sdkReady → ptInit → ready` handshake with a readiness guard so injected
  `setCenter/setPins/setUserMarker` calls never run before the SDK loads; report SDK
  load/init errors via an `{type:'error'}` message surfaced as visible text. Provide a
  local `mobile/.env` with a working `EXPO_PUBLIC_KAKAO_JS_KEY` (the legacy key
  `415220ee8c806e742408cdeef1fbedc9` is proven to have `https://localhost` registered;
  use it for the simulator verification and align `eas.json` to the same key if the
  current build key fails the domain check in-sim). Keep the existing `KakaoWebMap`
  prop contract (`center/pins/userLocation/onPinTap/onCenterChanged`).

## Non-goals

- No backend code changes (region completeness handled client-side; if the static
  tree later wants server parity, that is a separate task).
- No new native modules (CLAUDE.md prohibition). Map stays WebView + JS SDK.
- No redesign beyond the five named screens.

## Verification

- `cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test`.
- iOS simulator smoke (axe CLI for taps/swipes): splash → onboarding (swipe 3 steps +
  skip) → home → spot detail (all sections present) → map tab (Kakao tiles render,
  pins show) → region picker (left 33%, all districts, pick → recenters).

## Deploy

- Mobile: bump `app.json` version, tag `v0.3.x` to trigger EAS production build +
  TestFlight submit (per CI). `.env` is git-ignored; the build key lives in `eas.json`.
- Backend: no change expected; merging to `main` auto-deploys via CI regardless.
