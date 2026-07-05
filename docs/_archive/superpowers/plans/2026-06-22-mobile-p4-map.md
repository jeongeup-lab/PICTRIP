# P4 Map + Permission + Region-Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Map tab (mockup 11) — KakaoWebMap (WebView + Kakao JS SDK) with spot pins + a 3-snap bottom sheet list, plus the location-permission overlay (04) and the region-picker modal (12).

**Architecture:** A `src/features/map/` module holds a zustand `map-store` (single source of truth for center/anchor/category/label/snap), pure libs (category mapping, header-label formatter, haversine, search-here threshold, Kakao HTML builder), a `request-location` usecase, TanStack queries, and the WebView/sheet/overlay components. Thin `app/(tabs)/map.tsx` orchestrates them. The map degrades gracefully to a blank placeholder when no Kakao JS key is configured.

**Tech Stack:** Expo SDK 56 · RN 0.85 · React 19.2 · TS strict · Expo Router · zustand · TanStack Query · axios · `react-native-webview` (installed) · `expo-location` (installed) · RN `Animated`+`PanResponder` (no new native modules) · jest-expo.

## Global Constraints

- Design SSOT: `docs/mockups/04-permissions.html`·`11-map.html`·`12-region-picker.html`. Spec: `docs/superpowers/specs/2026-06-22-mobile-p4-map-design.md`. Locked decisions: `docs/specs/screens/S05-map-region.md`.
- **No emoji. Monochrome theme tokens only** (`src/constants/theme.ts`). ONLY color exception = the current-location marker blue dot `#2D7DF6` (functional marker, S05 §1.2). Congestion = monochrome text chip (한산/보통/붐빔), null hidden. Icons = line-SVG `<Icon>`.
- **No `as any`.** Use `as unknown as T` (matches `api-client.ts`).
- File naming: components PascalCase; runtime modules (api/lib/stores/usecases/queries/constants) kebab-case; `src/app/**` Expo Router.
- **JSend unwrapped once** in `api-client`; feature `api.ts` must NOT re-unwrap. UI branches on `err.code` (`AppError`), never `err.message`.
- **Map = KakaoWebMap (WebView + Kakao JS SDK)**; `@react-native-kakao/map` is forbidden.
- **No new native modules.** Bottom sheet = RN `Animated`+`PanResponder`. `react-native-webview`/`expo-location` are already installed; add NO dependencies.
- **DO NOT download/store KTO images** — `firstImageUrl` URLs only.
- **Secrets**: `EXPO_PUBLIC_KAKAO_JS_KEY` env only, never hard-coded.
- Verification (run in `mobile/` before declaring any task done): `npm run lint && npm run typecheck && npm run format:check && npm test`.
- Commit per task. **Do not push** unless explicitly asked.

## Backend contract (verified against `backend/app/modules/map/`)

- `GET /map/nearby?lat&lng&radius&category` → `NearbySpotCard[]` (distance asc, server-capped). Fields: `contentId, title, firstImageUrl, addr1, mapx, mapy, dist, category (subtype label), regionName, sigunguName, overview, congestion("low"|"medium"|"high"|null)`. `category` query param ∈ `attraction|food|cafe|leisure|shopping` (omit = 전체). `radius` default 3000.
- `GET /map/region?lat&lng` → `RegionLabel { sido, sigungu, dong, label }`.
- `GET /map/regions-tree` → `RegionNode[] { regionCode, regionName, centroid{lat,lng}, sigungus:[{ sigunguCode, sigunguName, centroid{lat,lng} }] }`.
- `mapx` = longitude, `mapy` = latitude (KTO convention).

---

### Task 1: Foundation — env, constants, region DTO types, chevron-down icon

**Files:**
- Modify: `mobile/src/constants/env.ts`
- Create: `mobile/src/constants/map.ts`
- Modify: `mobile/.env.example`
- Modify: `mobile/src/lib/api-types.ts`
- Modify: `mobile/src/components/Icon.tsx`
- Test: `mobile/src/components/__tests__/Icon.test.tsx` (extend)

**Interfaces:**
- Produces:
  - `KAKAO_JS_KEY: string` (`@/constants/env`)
  - `SEOUL_CITY_HALL`, `RADIUS_M=3000`, `NEARBY_CAP=30`, `SEARCH_HERE_RATIO=0.3` (`@/constants/map`)
  - `RegionLabel`, `Centroid`, `SigunguNode`, `RegionNode` interfaces (`@/lib/api-types`)
  - `IconName` addition: `"chevron-down"`.

- [ ] **Step 1: Add the Kakao JS key to env**

In `mobile/src/constants/env.ts`, append after the existing `API_BASE` line:
```ts
export const KAKAO_JS_KEY = process.env.EXPO_PUBLIC_KAKAO_JS_KEY ?? "";
```

- [ ] **Step 2: Create map constants**

Create `mobile/src/constants/map.ts`:
```ts
/** Seoul City Hall — degraded map center when GPS is unavailable (S05 §0). */
export const SEOUL_CITY_HALL = { lat: 37.5666, lng: 126.9784 } as const;

/** Fixed query radius in metres (S05 §0; no UI control). */
export const RADIUS_M = 3000;

/** Max nearby cards rendered (S05 §0). */
export const NEARBY_CAP = 30;

/** "이 지역에서 검색" appears once the viewport drifts this fraction of the
 * radius from the last query center (S05 §1.4 ~30%). */
export const SEARCH_HERE_RATIO = 0.3;
```

- [ ] **Step 3: Add the Kakao key to `.env.example`**

In `mobile/.env.example`, append:
```bash
# Kakao Maps JavaScript app key (KakaoWebMap WebView). Blank → map renders a
# blank placeholder; list/permission/picker still work. See spec §9.
EXPO_PUBLIC_KAKAO_JS_KEY=
```

- [ ] **Step 4: Add region DTO types**

Append to `mobile/src/lib/api-types.ts` (after the existing `NearbySpot` interface):
```ts
export interface RegionLabel {
  sido: string | null;
  sigungu: string | null;
  dong: string | null;
  label: string;
}

export interface Centroid {
  lat: number;
  lng: number;
}

export interface SigunguNode {
  sigunguCode: string;
  sigunguName: string;
  centroid: Centroid;
}

export interface RegionNode {
  regionCode: string;
  regionName: string;
  centroid: Centroid;
  sigungus: SigunguNode[];
}
```

- [ ] **Step 5: Add the chevron-down icon**

In `mobile/src/components/Icon.tsx`, add to the `IconName` union (after `"chevron-right"`):
```ts
  | "chevron-down"
```
Add to the `PATHS` record:
```ts
  "chevron-down": { d: "M6 9l6 6 6-6" },
```

- [ ] **Step 6: Extend the Icon render test**

In `mobile/src/components/__tests__/Icon.test.tsx`, add inside the `describe`:
```tsx
  it("renders chevron-down", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<Icon name="chevron-down" />);
    });
    expect(r!.toJSON()).toBeTruthy();
  });
```

- [ ] **Step 7: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/src/constants/env.ts mobile/src/constants/map.ts mobile/.env.example mobile/src/lib/api-types.ts mobile/src/components/Icon.tsx mobile/src/components/__tests__/Icon.test.tsx
git commit -m "feat(mobile): P4 foundation — kakao js key env, map constants, region DTOs, chevron-down"
```

---

### Task 2: Category chips lib

**Files:**
- Create: `mobile/src/features/map/lib/nearby-categories.ts`
- Test: `mobile/src/features/map/lib/__tests__/nearby-categories.test.ts`

**Interfaces:**
- Produces:
  - `type NearbyCategory = "attraction" | "food" | "cafe" | "leisure" | "shopping"`
  - `interface CategoryChip { label: string; value: NearbyCategory | null }`
  - `CATEGORY_CHIPS: CategoryChip[]` (전체 first, value `null`)

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/map/lib/__tests__/nearby-categories.test.ts`:
```ts
import { CATEGORY_CHIPS } from "@/features/map/lib/nearby-categories";

describe("CATEGORY_CHIPS", () => {
  it("starts with 전체 mapped to null", () => {
    expect(CATEGORY_CHIPS[0]).toEqual({ label: "전체", value: null });
  });
  it("maps the five KTO buckets to backend NearbyCategory values", () => {
    const byLabel = Object.fromEntries(CATEGORY_CHIPS.map((c) => [c.label, c.value]));
    expect(byLabel["관광지"]).toBe("attraction");
    expect(byLabel["음식점"]).toBe("food");
    expect(byLabel["카페"]).toBe("cafe");
    expect(byLabel["레저"]).toBe("leisure");
    expect(byLabel["쇼핑"]).toBe("shopping");
  });
  it("has exactly six chips", () => {
    expect(CATEGORY_CHIPS).toHaveLength(6);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/map/lib/__tests__/nearby-categories.test.ts`
Expected: FAIL — cannot find module `nearby-categories`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/map/lib/nearby-categories.ts`:
```ts
/** Single-select map category chips. Values are 1:1 with the backend
 * NearbyCategory enum (spots/services/nearby.py); 전체 omits the param. */
export type NearbyCategory = "attraction" | "food" | "cafe" | "leisure" | "shopping";

export interface CategoryChip {
  label: string;
  value: NearbyCategory | null;
}

export const CATEGORY_CHIPS: CategoryChip[] = [
  { label: "전체", value: null },
  { label: "관광지", value: "attraction" },
  { label: "음식점", value: "food" },
  { label: "카페", value: "cafe" },
  { label: "레저", value: "leisure" },
  { label: "쇼핑", value: "shopping" },
];
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/map/lib/__tests__/nearby-categories.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/map/lib/nearby-categories.ts mobile/src/features/map/lib/__tests__/nearby-categories.test.ts
git commit -m "feat(mobile): map category chip mapping (NearbyCategory)"
```

---

### Task 3: Geo distance + search-here threshold libs

**Files:**
- Create: `mobile/src/features/map/lib/geo.ts`
- Create: `mobile/src/features/map/lib/search-here.ts`
- Test: `mobile/src/features/map/lib/__tests__/geo.test.ts`
- Test: `mobile/src/features/map/lib/__tests__/search-here.test.ts`

**Interfaces:**
- Consumes: `SEARCH_HERE_RATIO`, `RADIUS_M` (`@/constants/map`).
- Produces:
  - `interface LatLng { lat: number; lng: number }`
  - `haversineMeters(a: LatLng, b: LatLng): number` (`@/features/map/lib/geo`)
  - `shouldShowSearchHere(viewport: LatLng | null, lastQuery: LatLng | null, radius: number): boolean` (`@/features/map/lib/search-here`)

- [ ] **Step 1: Write the failing geo test**

Create `mobile/src/features/map/lib/__tests__/geo.test.ts`:
```ts
import { haversineMeters } from "@/features/map/lib/geo";

describe("haversineMeters", () => {
  it("is zero for identical points", () => {
    expect(haversineMeters({ lat: 37.5, lng: 127 }, { lat: 37.5, lng: 127 })).toBe(0);
  });
  it("approximates a known short distance (~1.11km per 0.01° lat)", () => {
    const d = haversineMeters({ lat: 37.5, lng: 127 }, { lat: 37.51, lng: 127 });
    expect(d).toBeGreaterThan(1100);
    expect(d).toBeLessThan(1120);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/map/lib/__tests__/geo.test.ts`
Expected: FAIL — cannot find module `geo`.

- [ ] **Step 3: Implement geo**

Create `mobile/src/features/map/lib/geo.ts`:
```ts
export interface LatLng {
  lat: number;
  lng: number;
}

const R = 6371000; // earth radius, metres
const rad = (d: number) => (d * Math.PI) / 180;

/** Great-circle distance in metres between two coordinates. */
export function haversineMeters(a: LatLng, b: LatLng): number {
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}
```

- [ ] **Step 4: Run geo test**

Run: `npx jest src/features/map/lib/__tests__/geo.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Write the failing search-here test**

Create `mobile/src/features/map/lib/__tests__/search-here.test.ts`:
```ts
import { shouldShowSearchHere } from "@/features/map/lib/search-here";

describe("shouldShowSearchHere", () => {
  const base = { lat: 37.5, lng: 127 };
  it("is false when either point is null", () => {
    expect(shouldShowSearchHere(null, base, 3000)).toBe(false);
    expect(shouldShowSearchHere(base, null, 3000)).toBe(false);
  });
  it("is false for a small drift (< 30% of radius)", () => {
    // ~111m north — well under 900m threshold
    expect(shouldShowSearchHere({ lat: 37.501, lng: 127 }, base, 3000)).toBe(false);
  });
  it("is true once drift exceeds 30% of radius", () => {
    // ~1.1km north — over the 900m threshold
    expect(shouldShowSearchHere({ lat: 37.51, lng: 127 }, base, 3000)).toBe(true);
  });
});
```

- [ ] **Step 6: Run test to verify it fails**

Run: `npx jest src/features/map/lib/__tests__/search-here.test.ts`
Expected: FAIL — cannot find module `search-here`.

- [ ] **Step 7: Implement search-here**

Create `mobile/src/features/map/lib/search-here.ts`:
```ts
import { SEARCH_HERE_RATIO } from "@/constants/map";
import { haversineMeters, type LatLng } from "@/features/map/lib/geo";

/** True when the panned viewport center has drifted past SEARCH_HERE_RATIO of
 * the query radius from the last fetched center — the cue to surface the
 * "이 지역에서 검색" pill (S05 §1.4). */
export function shouldShowSearchHere(
  viewport: LatLng | null,
  lastQuery: LatLng | null,
  radius: number,
): boolean {
  if (!viewport || !lastQuery) return false;
  return haversineMeters(viewport, lastQuery) > radius * SEARCH_HERE_RATIO;
}
```

- [ ] **Step 8: Run search-here test**

Run: `npx jest src/features/map/lib/__tests__/search-here.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 9: Commit**

```bash
git add mobile/src/features/map/lib/geo.ts mobile/src/features/map/lib/search-here.ts mobile/src/features/map/lib/__tests__/geo.test.ts mobile/src/features/map/lib/__tests__/search-here.test.ts
git commit -m "feat(mobile): haversine + search-here threshold libs"
```

---

### Task 4: Header label formatter lib

**Files:**
- Create: `mobile/src/features/map/lib/region-label.ts`
- Test: `mobile/src/features/map/lib/__tests__/region-label.test.ts`

**Interfaces:**
- Consumes: `RegionLabel` (`@/lib/api-types`).
- Produces:
  - `type AnchorSource = "gps" | "region" | "pan"`
  - `formatHeaderLabel(source: AnchorSource, label: RegionLabel | null): string` — gps → `현위치 · {dong||label}`; region/pan → `{label}` (no prefix); null → `위치 확인 중`.

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/map/lib/__tests__/region-label.test.ts`:
```ts
import { formatHeaderLabel } from "@/features/map/lib/region-label";
import type { RegionLabel } from "@/lib/api-types";

const seoul: RegionLabel = { sido: "서울", sigungu: "중구", dong: "명동", label: "서울 중구 명동" };

describe("formatHeaderLabel", () => {
  it("prefixes 현위치 with the dong when GPS-anchored", () => {
    expect(formatHeaderLabel("gps", seoul)).toBe("현위치 · 명동");
  });
  it("falls back to label when GPS-anchored without a dong", () => {
    expect(formatHeaderLabel("gps", { ...seoul, dong: null })).toBe("현위치 · 서울 중구 명동");
  });
  it("shows the plain label (no prefix) for region/pan anchors", () => {
    expect(formatHeaderLabel("region", seoul)).toBe("서울 중구 명동");
    expect(formatHeaderLabel("pan", seoul)).toBe("서울 중구 명동");
  });
  it("shows a placeholder when label is null", () => {
    expect(formatHeaderLabel("gps", null)).toBe("위치 확인 중");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/map/lib/__tests__/region-label.test.ts`
Expected: FAIL — cannot find module `region-label`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/map/lib/region-label.ts`:
```ts
import type { RegionLabel } from "@/lib/api-types";

export type AnchorSource = "gps" | "region" | "pan";

/** Header label per S05 §0 rule 4: GPS shows a `현위치 · {동}` prefix; region
 * selection / pan-search show the bare region name. */
export function formatHeaderLabel(source: AnchorSource, label: RegionLabel | null): string {
  if (!label) return "위치 확인 중";
  if (source === "gps") return `현위치 · ${label.dong ?? label.label}`;
  return label.label;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/map/lib/__tests__/region-label.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/map/lib/region-label.ts mobile/src/features/map/lib/__tests__/region-label.test.ts
git commit -m "feat(mobile): map header label formatter (gps prefix vs region name)"
```

---

### Task 5: Kakao map HTML builder lib

**Files:**
- Create: `mobile/src/features/map/lib/kakao-map-html.ts`
- Test: `mobile/src/features/map/lib/__tests__/kakao-map-html.test.ts`

**Interfaces:**
- Consumes: `SEOUL_CITY_HALL` (`@/constants/map`).
- Produces: `buildKakaoMapHtml(jsKey: string): string` — a full HTML document embedding the Kakao JS SDK (`autoload=false`) and the RN↔WebView bridge.

> Bridge protocol (consumed by `KakaoWebMap.tsx`, Task 11):
> - RN → WebView (`injectJavaScript`): global fns `setCenter(lat,lng)`, `setPins(spotsJsonArray)`, `setUserMarker(lat,lng)` (lat null clears), `recenter()` is unused (RN calls setCenter).
> - WebView → RN (`postMessage`): `{type:"ready"}`, `{type:"pin_tap",payload:{contentId}}`, `{type:"center_changed",payload:{lat,lng}}`.

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/map/lib/__tests__/kakao-map-html.test.ts`:
```ts
import { buildKakaoMapHtml } from "@/features/map/lib/kakao-map-html";

describe("buildKakaoMapHtml", () => {
  const html = buildKakaoMapHtml("TESTKEY123");
  it("embeds the provided app key", () => {
    expect(html).toContain("appkey=TESTKEY123");
  });
  it("loads the SDK with autoload=false", () => {
    expect(html).toContain("dapi.kakao.com/v2/maps/sdk.js");
    expect(html).toContain("autoload=false");
    expect(html).toContain("kakao.maps.load");
  });
  it("wires the bridge message handlers", () => {
    expect(html).toContain("ReactNativeWebView");
    expect(html).toContain("center_changed");
    expect(html).toContain("pin_tap");
    expect(html).toContain("setPins");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/map/lib/__tests__/kakao-map-html.test.ts`
Expected: FAIL — cannot find module `kakao-map-html`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/map/lib/kakao-map-html.ts`:
```ts
import { SEOUL_CITY_HALL } from "@/constants/map";

/** Build the self-contained HTML for the KakaoWebMap WebView. The Kakao JS SDK
 * is loaded with autoload=false and initialized in kakao.maps.load(). Markers
 * are CustomOverlays: ink teardrop pins + a blue current-location dot (the one
 * sanctioned color, S05 §1.2). Bridges via window.ReactNativeWebView. */
export function buildKakaoMapHtml(jsKey: string): string {
  const { lat, lng } = SEOUL_CITY_HALL;
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
<style>
  html,body,#map{margin:0;padding:0;width:100%;height:100%;overflow:hidden}
  .pin{width:18px;height:18px;background:#171719;border:2px solid #fff;border-radius:50% 50% 50% 0;transform:rotate(-45deg);box-shadow:0 1px 3px rgba(0,0,0,.3)}
  .me{width:16px;height:16px;background:#2D7DF6;border:3px solid #fff;border-radius:50%;box-shadow:0 0 0 6px rgba(45,125,246,.25)}
</style>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey=${jsKey}&autoload=false"></script>
</head>
<body>
<div id="map"></div>
<script>
  var map, pins = [], me = null;
  function post(type, payload){ if(window.ReactNativeWebView){ window.ReactNativeWebView.postMessage(JSON.stringify({type:type,payload:payload||{}})); } }
  function clearPins(){ pins.forEach(function(o){ o.setMap(null); }); pins = []; }
  function setCenter(lat,lng){ if(map){ map.setCenter(new kakao.maps.LatLng(lat,lng)); } }
  function setPins(spots){
    if(!map) return; clearPins();
    spots.forEach(function(s){
      if(s.mapy==null||s.mapx==null) return;
      var el = document.createElement('div'); el.className='pin';
      var ov = new kakao.maps.CustomOverlay({ position:new kakao.maps.LatLng(s.mapy,s.mapx), content:el, yAnchor:1 });
      ov.setMap(map);
      el.addEventListener('click', function(){ post('pin_tap',{contentId:s.contentId}); });
      pins.push(ov);
    });
  }
  function setUserMarker(lat,lng){
    if(me){ me.setMap(null); me=null; }
    if(lat==null||!map) return;
    var el = document.createElement('div'); el.className='me';
    me = new kakao.maps.CustomOverlay({ position:new kakao.maps.LatLng(lat,lng), content:el });
    me.setMap(map);
  }
  function handle(e){ try{ var m = JSON.parse(e.data);
    if(m.cmd==='setCenter') setCenter(m.lat,m.lng);
    else if(m.cmd==='setPins') setPins(m.spots);
    else if(m.cmd==='setUserMarker') setUserMarker(m.lat,m.lng);
  }catch(_){} }
  document.addEventListener('message', handle);
  window.addEventListener('message', handle);
  kakao.maps.load(function(){
    map = new kakao.maps.Map(document.getElementById('map'), { center:new kakao.maps.LatLng(${lat},${lng}), level:6 });
    kakao.maps.event.addListener(map,'dragend',function(){ var c=map.getCenter(); post('center_changed',{lat:c.getLat(),lng:c.getLng()}); });
    post('ready');
  });
</script>
</body>
</html>`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/map/lib/__tests__/kakao-map-html.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/map/lib/kakao-map-html.ts mobile/src/features/map/lib/__tests__/kakao-map-html.test.ts
git commit -m "feat(mobile): kakao map HTML builder (SDK autoload=false + RN bridge)"
```

---

### Task 6: Map API

**Files:**
- Create: `mobile/src/features/map/api.ts`
- Test: `mobile/src/features/map/__tests__/api.test.ts`

**Interfaces:**
- Consumes: `api` (`@/lib/api-client`), `NearbySpot`/`RegionLabel`/`RegionNode` (`@/lib/api-types`), `RADIUS_M` (`@/constants/map`), `NearbyCategory` (`@/features/map/lib/nearby-categories`).
- Produces:
  - `getNearby(lat: number, lng: number, category?: NearbyCategory | null): Promise<NearbySpot[]>`
  - `getRegionLabel(lat: number, lng: number): Promise<RegionLabel>`
  - `getRegionsTree(): Promise<RegionNode[]>`

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/map/__tests__/api.test.ts`:
```ts
jest.mock("@/lib/api-client", () => ({ api: { get: jest.fn() } }));

import { api } from "@/lib/api-client";
import { getNearby, getRegionLabel, getRegionsTree } from "@/features/map/api";

describe("map api", () => {
  beforeEach(() => jest.clearAllMocks());

  it("getNearby sends lat/lng/radius and category when given", async () => {
    (api.get as jest.Mock).mockResolvedValue([]);
    await getNearby(37.5, 127, "cafe");
    expect(api.get).toHaveBeenCalledWith("/map/nearby", {
      params: { lat: 37.5, lng: 127, radius: 3000, category: "cafe" },
    });
  });

  it("getNearby omits category when null", async () => {
    (api.get as jest.Mock).mockResolvedValue([]);
    await getNearby(37.5, 127, null);
    expect(api.get).toHaveBeenCalledWith("/map/nearby", {
      params: { lat: 37.5, lng: 127, radius: 3000, category: undefined },
    });
  });

  it("getRegionLabel sends lat/lng", async () => {
    (api.get as jest.Mock).mockResolvedValue({ label: "서울 중구" });
    const r = await getRegionLabel(37.5, 127);
    expect(api.get).toHaveBeenCalledWith("/map/region", { params: { lat: 37.5, lng: 127 } });
    expect(r.label).toBe("서울 중구");
  });

  it("getRegionsTree calls the tree endpoint", async () => {
    (api.get as jest.Mock).mockResolvedValue([]);
    await getRegionsTree();
    expect(api.get).toHaveBeenCalledWith("/map/regions-tree");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/map/__tests__/api.test.ts`
Expected: FAIL — cannot find module `api`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/map/api.ts`:
```ts
import { api } from "@/lib/api-client";
import type { NearbySpot, RegionLabel, RegionNode } from "@/lib/api-types";
import { RADIUS_M } from "@/constants/map";
import type { NearbyCategory } from "@/features/map/lib/nearby-categories";

/** Nearby spots within RADIUS_M (server sorts by distance asc + caps). 전체 =
 * omit category. api-client unwraps JSend once. */
export async function getNearby(
  lat: number,
  lng: number,
  category?: NearbyCategory | null,
): Promise<NearbySpot[]> {
  return (await api.get("/map/nearby", {
    params: { lat, lng, radius: RADIUS_M, category: category ?? undefined },
  })) as unknown as NearbySpot[];
}

/** Reverse-geocoded region label for the header (Kakao coord2regioncode). */
export async function getRegionLabel(lat: number, lng: number): Promise<RegionLabel> {
  return (await api.get("/map/region", { params: { lat, lng } })) as unknown as RegionLabel;
}

/** 17 시도 → 시군구 tree with runtime-AVG centroids (static; cache-friendly). */
export async function getRegionsTree(): Promise<RegionNode[]> {
  return (await api.get("/map/regions-tree")) as unknown as RegionNode[];
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/map/__tests__/api.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/map/api.ts mobile/src/features/map/__tests__/api.test.ts
git commit -m "feat(mobile): map api (nearby + region label + regions tree)"
```

---

### Task 7: Location permission usecase

**Files:**
- Create: `mobile/src/features/map/usecases/request-location.ts`
- Test: `mobile/src/features/map/usecases/__tests__/request-location.test.ts`

**Interfaces:**
- Consumes: `expo-location`.
- Produces:
  - `type PermStatus = "granted" | "denied" | "undetermined"`
  - `interface Coords { lat: number; lng: number }`
  - `getPermissionStatus(): Promise<PermStatus>` (read-only)
  - `requestPermission(): Promise<PermStatus>` (prompts)
  - `getCurrentCoords(): Promise<Coords | null>`

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/map/usecases/__tests__/request-location.test.ts`:
```ts
jest.mock("expo-location", () => ({
  getForegroundPermissionsAsync: jest.fn(),
  requestForegroundPermissionsAsync: jest.fn(),
  getCurrentPositionAsync: jest.fn(),
}));

import * as Location from "expo-location";
import {
  getPermissionStatus,
  requestPermission,
  getCurrentCoords,
} from "@/features/map/usecases/request-location";

describe("request-location", () => {
  beforeEach(() => jest.clearAllMocks());

  it("getPermissionStatus maps the expo status string", async () => {
    (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ status: "undetermined" });
    expect(await getPermissionStatus()).toBe("undetermined");
  });

  it("requestPermission prompts and maps granted", async () => {
    (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ status: "granted" });
    expect(await requestPermission()).toBe("granted");
    expect(Location.requestForegroundPermissionsAsync).toHaveBeenCalled();
  });

  it("getCurrentCoords returns lat/lng on success", async () => {
    (Location.getCurrentPositionAsync as jest.Mock).mockResolvedValue({
      coords: { latitude: 37.5, longitude: 127.0 },
    });
    expect(await getCurrentCoords()).toEqual({ lat: 37.5, lng: 127.0 });
  });

  it("getCurrentCoords returns null when the fix throws", async () => {
    (Location.getCurrentPositionAsync as jest.Mock).mockRejectedValue(new Error("timeout"));
    expect(await getCurrentCoords()).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/map/usecases/__tests__/request-location.test.ts`
Expected: FAIL — cannot find module `request-location`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/map/usecases/request-location.ts`:
```ts
import * as Location from "expo-location";

export type PermStatus = "granted" | "denied" | "undetermined";

export interface Coords {
  lat: number;
  lng: number;
}

function toStatus(s: Location.PermissionStatus | string): PermStatus {
  if (s === "granted") return "granted";
  if (s === "undetermined") return "undetermined";
  return "denied";
}

/** Read current permission without prompting (S05 entry branch). */
export async function getPermissionStatus(): Promise<PermStatus> {
  const { status } = await Location.getForegroundPermissionsAsync();
  return toStatus(status);
}

/** Prompt for permission (priming "위치 허용하기"). */
export async function requestPermission(): Promise<PermStatus> {
  const { status } = await Location.requestForegroundPermissionsAsync();
  return toStatus(status);
}

/** Best-effort current GPS fix; null on failure. */
export async function getCurrentCoords(): Promise<Coords | null> {
  try {
    const pos = await Location.getCurrentPositionAsync();
    return { lat: pos.coords.latitude, lng: pos.coords.longitude };
  } catch {
    return null;
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/map/usecases/__tests__/request-location.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/map/usecases/request-location.ts mobile/src/features/map/usecases/__tests__/request-location.test.ts
git commit -m "feat(mobile): location permission usecase (status/request/coords)"
```

---

### Task 8: Map store

**Files:**
- Create: `mobile/src/features/map/stores/map-store.ts`
- Test: `mobile/src/features/map/stores/__tests__/map-store.test.ts`

**Interfaces:**
- Consumes: `LatLng` (`@/features/map/lib/geo`), `AnchorSource` (`@/features/map/lib/region-label`), `NearbyCategory` (`@/features/map/lib/nearby-categories`), `RegionLabel` (`@/lib/api-types`), `shouldShowSearchHere` (`@/features/map/lib/search-here`), `RADIUS_M` (`@/constants/map`).
- Produces: `useMapStore` (zustand) with state `{ center, anchorSource, category, gpsCoords, label, snap, viewportCenter, lastQueryCenter, selectedSpotId }` and actions `setAnchor(center, source, gps?)`, `setLabel(label)`, `setCategory(c)`, `onViewportChange(c)`, `searchHere()`, `recenterToGps()`, `applyRegion(centroid)`, `setSnap(s)`, `selectSpot(id)`, `pillVisible()`, `reset()`.

> `setAnchor` records `center` + `lastQueryCenter` (a fetch will follow) and clears the pill. `searchHere`/`applyRegion`/`recenterToGps` are thin wrappers over `setAnchor` with the right source. `pillVisible()` derives from `shouldShowSearchHere(viewportCenter, lastQueryCenter, RADIUS_M)`.

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/map/stores/__tests__/map-store.test.ts`:
```ts
import { useMapStore } from "@/features/map/stores/map-store";

const seoul = { lat: 37.5666, lng: 126.9784 };

describe("map-store", () => {
  beforeEach(() => useMapStore.getState().reset());

  it("setAnchor sets center, source, and lastQueryCenter; pill hidden", () => {
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    const s = useMapStore.getState();
    expect(s.center).toEqual(seoul);
    expect(s.anchorSource).toBe("gps");
    expect(s.gpsCoords).toEqual(seoul);
    expect(s.lastQueryCenter).toEqual(seoul);
    expect(s.pillVisible()).toBe(false);
  });

  it("onViewportChange beyond threshold makes the pill visible without moving center", () => {
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    useMapStore.getState().onViewportChange({ lat: 37.58, lng: 126.9784 }); // ~1.5km north
    expect(useMapStore.getState().pillVisible()).toBe(true);
    expect(useMapStore.getState().center).toEqual(seoul); // unchanged
  });

  it("searchHere promotes the viewport to center with source=pan and hides the pill", () => {
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    const vp = { lat: 37.58, lng: 126.9784 };
    useMapStore.getState().onViewportChange(vp);
    useMapStore.getState().searchHere();
    const s = useMapStore.getState();
    expect(s.center).toEqual(vp);
    expect(s.anchorSource).toBe("pan");
    expect(s.pillVisible()).toBe(false);
  });

  it("applyRegion centers on the centroid with source=region", () => {
    const c = { lat: 35.1, lng: 129.0 };
    useMapStore.getState().applyRegion(c);
    expect(useMapStore.getState().center).toEqual(c);
    expect(useMapStore.getState().anchorSource).toBe("region");
  });

  it("recenterToGps returns to gps coords with source=gps", () => {
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    useMapStore.getState().applyRegion({ lat: 35, lng: 129 });
    useMapStore.getState().recenterToGps();
    const s = useMapStore.getState();
    expect(s.center).toEqual(seoul);
    expect(s.anchorSource).toBe("gps");
  });

  it("recenterToGps is a no-op when there is no gps fix", () => {
    useMapStore.getState().applyRegion({ lat: 35, lng: 129 });
    useMapStore.getState().recenterToGps();
    expect(useMapStore.getState().anchorSource).toBe("region");
  });

  it("setCategory changes category without moving center", () => {
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    useMapStore.getState().setCategory("cafe");
    expect(useMapStore.getState().category).toBe("cafe");
    expect(useMapStore.getState().center).toEqual(seoul);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/map/stores/__tests__/map-store.test.ts`
Expected: FAIL — cannot find module `map-store`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/map/stores/map-store.ts`:
```ts
import { create } from "zustand";
import type { LatLng } from "@/features/map/lib/geo";
import type { AnchorSource } from "@/features/map/lib/region-label";
import type { NearbyCategory } from "@/features/map/lib/nearby-categories";
import type { RegionLabel } from "@/lib/api-types";
import { shouldShowSearchHere } from "@/features/map/lib/search-here";
import { RADIUS_M } from "@/constants/map";

type Snap = "peek" | "half" | "full";

interface MapState {
  center: LatLng | null;
  anchorSource: AnchorSource;
  category: NearbyCategory | null;
  gpsCoords: LatLng | null;
  label: RegionLabel | null;
  snap: Snap;
  viewportCenter: LatLng | null;
  lastQueryCenter: LatLng | null;
  selectedSpotId: string | null;
  setAnchor: (center: LatLng, source: AnchorSource, gps?: LatLng | null) => void;
  setLabel: (label: RegionLabel | null) => void;
  setCategory: (c: NearbyCategory | null) => void;
  onViewportChange: (c: LatLng) => void;
  searchHere: () => void;
  recenterToGps: () => void;
  applyRegion: (centroid: LatLng) => void;
  setSnap: (s: Snap) => void;
  selectSpot: (id: string | null) => void;
  pillVisible: () => boolean;
  reset: () => void;
}

const initial = {
  center: null,
  anchorSource: "gps" as AnchorSource,
  category: null,
  gpsCoords: null,
  label: null,
  snap: "half" as Snap,
  viewportCenter: null,
  lastQueryCenter: null,
  selectedSpotId: null,
};

/** Single source of truth for the map tab. Center/anchor drive the nearby
 * fetch (queries read center+category); panning only updates viewportCenter so
 * the pill can appear without refetching (S05 §1.3-1.4). */
export const useMapStore = create<MapState>((set, get) => ({
  ...initial,

  setAnchor: (center, source, gps) =>
    set((s) => ({
      center,
      anchorSource: source,
      gpsCoords: gps !== undefined ? gps : s.gpsCoords,
      lastQueryCenter: center,
      viewportCenter: center,
    })),

  setLabel: (label) => set({ label }),
  setCategory: (category) => set({ category }),
  onViewportChange: (viewportCenter) => set({ viewportCenter }),

  searchHere: () => {
    const vp = get().viewportCenter;
    if (!vp) return;
    get().setAnchor(vp, "pan");
  },

  recenterToGps: () => {
    const gps = get().gpsCoords;
    if (!gps) return;
    get().setAnchor(gps, "gps", gps);
  },

  applyRegion: (centroid) => get().setAnchor(centroid, "region"),

  setSnap: (snap) => set({ snap }),
  selectSpot: (selectedSpotId) => set({ selectedSpotId }),

  pillVisible: () => shouldShowSearchHere(get().viewportCenter, get().lastQueryCenter, RADIUS_M),

  reset: () => set({ ...initial }),
}));
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/map/stores/__tests__/map-store.test.ts`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/map/stores/map-store.ts mobile/src/features/map/stores/__tests__/map-store.test.ts
git commit -m "feat(mobile): map store (center/anchor/category/pill transitions)"
```

---

### Task 9: Map queries

**Files:**
- Create: `mobile/src/features/map/queries.ts`

> Hooks are not unit-tested (no renderHook in this project); gate = lint + typecheck + format + suite green.

**Interfaces:**
- Consumes: `getNearby`/`getRegionLabel`/`getRegionsTree` (Task 6), `LatLng` (`@/features/map/lib/geo`), `NearbyCategory` (Task 2).
- Produces: `useNearbyMap(center, category)`, `useRegionLabel(center, enabled)`, `useRegionsTree()`.

- [ ] **Step 1: Write the queries**

Create `mobile/src/features/map/queries.ts`:
```ts
import { useQuery } from "@tanstack/react-query";
import type { LatLng } from "@/features/map/lib/geo";
import type { NearbyCategory } from "@/features/map/lib/nearby-categories";
import { getNearby, getRegionLabel, getRegionsTree } from "@/features/map/api";

/** Nearby spots for the current center + category. Disabled until a center exists. */
export function useNearbyMap(center: LatLng | null, category: NearbyCategory | null) {
  return useQuery({
    queryKey: ["map-nearby", center?.lat, center?.lng, category],
    queryFn: () => getNearby(center!.lat, center!.lng, category),
    enabled: center != null,
  });
}

/** Reverse-geocoded header label for the current center. */
export function useRegionLabel(center: LatLng | null, enabled: boolean) {
  return useQuery({
    queryKey: ["region-label", center?.lat, center?.lng],
    queryFn: () => getRegionLabel(center!.lat, center!.lng),
    enabled: enabled && center != null,
  });
}

/** Static 시도/시군구 tree — cached long (rarely changes). */
export function useRegionsTree() {
  return useQuery({
    queryKey: ["regions-tree"],
    queryFn: getRegionsTree,
    staleTime: 24 * 60 * 60 * 1000,
  });
}
```

- [ ] **Step 2: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/src/features/map/queries.ts
git commit -m "feat(mobile): map queries (nearby, region label, regions tree)"
```

---

### Task 10: KakaoWebMap component

**Files:**
- Create: `mobile/src/features/map/components/KakaoWebMap.tsx`

> Not unit-tested (WebView); gate = lint + typecheck + format + suite green + manual smoke.

**Interfaces:**
- Consumes: `react-native-webview`, `buildKakaoMapHtml` (Task 5), `KAKAO_JS_KEY` (`@/constants/env`), `LatLng` (`@/features/map/lib/geo`), `NearbySpot` (`@/lib/api-types`), theme tokens.
- Produces: `KakaoWebMap({ center, pins, userLocation, onReady, onPinTap, onCenterChanged })` where `center: LatLng | null`, `pins: NearbySpot[]`, `userLocation: LatLng | null`, `onPinTap: (contentId: string) => void`, `onCenterChanged: (c: LatLng) => void`, `onReady?: () => void`. Imperative-free: it pushes `center`/`pins`/`userLocation` into the WebView via effects.

- [ ] **Step 1: Build the component**

Create `mobile/src/features/map/components/KakaoWebMap.tsx`:
```tsx
import { useEffect, useRef } from "react";
import { View, Text, StyleSheet } from "react-native";
import { WebView, type WebViewMessageEvent } from "react-native-webview";
import { buildKakaoMapHtml } from "@/features/map/lib/kakao-map-html";
import { KAKAO_JS_KEY } from "@/constants/env";
import type { LatLng } from "@/features/map/lib/geo";
import type { NearbySpot } from "@/lib/api-types";
import { colors, spacing } from "@/constants/theme";

interface Props {
  center: LatLng | null;
  pins: NearbySpot[];
  userLocation: LatLng | null;
  onReady?: () => void;
  onPinTap: (contentId: string) => void;
  onCenterChanged: (c: LatLng) => void;
}

export function KakaoWebMap({ center, pins, userLocation, onReady, onPinTap, onCenterChanged }: Props) {
  const ref = useRef<WebView>(null);
  const ready = useRef(false);

  const send = (cmd: object) => ref.current?.injectJavaScript(`window.handle({data:'${JSON.stringify(cmd)}'});true;`);

  useEffect(() => {
    if (ready.current && center) send({ cmd: "setCenter", lat: center.lat, lng: center.lng });
  }, [center]);
  useEffect(() => {
    if (ready.current) send({ cmd: "setPins", spots: pins.map((p) => ({ contentId: p.contentId, mapx: p.mapx, mapy: p.mapy })) });
  }, [pins]);
  useEffect(() => {
    if (ready.current) send({ cmd: "setUserMarker", lat: userLocation?.lat ?? null, lng: userLocation?.lng ?? null });
  }, [userLocation]);

  const onMessage = (e: WebViewMessageEvent) => {
    try {
      const m = JSON.parse(e.nativeEvent.data) as { type: string; payload?: Record<string, number | string> };
      if (m.type === "ready") {
        ready.current = true;
        if (center) send({ cmd: "setCenter", lat: center.lat, lng: center.lng });
        send({ cmd: "setPins", spots: pins.map((p) => ({ contentId: p.contentId, mapx: p.mapx, mapy: p.mapy })) });
        send({ cmd: "setUserMarker", lat: userLocation?.lat ?? null, lng: userLocation?.lng ?? null });
        onReady?.();
      } else if (m.type === "pin_tap" && m.payload) {
        onPinTap(String(m.payload.contentId));
      } else if (m.type === "center_changed" && m.payload) {
        onCenterChanged({ lat: Number(m.payload.lat), lng: Number(m.payload.lng) });
      }
    } catch {
      // ignore malformed bridge messages
    }
  };

  // Graceful degrade: no JS key → blank placeholder (list/permission/picker still work).
  if (!KAKAO_JS_KEY) {
    return (
      <View style={styles.placeholder}>
        <Text style={styles.placeholderText}>지도를 표시하려면 Kakao 지도 키가 필요해요</Text>
      </View>
    );
  }

  return (
    <WebView
      ref={ref}
      style={styles.web}
      originWhitelist={["*"]}
      source={{ html: buildKakaoMapHtml(KAKAO_JS_KEY) }}
      onMessage={onMessage}
      javaScriptEnabled
      domStorageEnabled
      scrollEnabled={false}
    />
  );
}

const styles = StyleSheet.create({
  web: { flex: 1, backgroundColor: colors.inset },
  placeholder: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.inset, padding: spacing.xl },
  placeholderText: { color: colors.ter, fontSize: 14, textAlign: "center" },
});
```

- [ ] **Step 2: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/src/features/map/components/KakaoWebMap.tsx
git commit -m "feat(mobile): KakaoWebMap WebView bridge (+ keyless degrade)"
```

---

### Task 11: MapBottomSheet component (3-snap)

**Files:**
- Create: `mobile/src/features/map/components/MapBottomSheet.tsx`

> Not unit-tested (gesture/Animated); gate = lint + typecheck + format + suite green + manual smoke.

**Interfaces:**
- Consumes: RN `Animated`/`PanResponder`/`Dimensions`, theme tokens.
- Produces: `MapBottomSheet({ snap, onSnapChange, headerExtra, children })` where `snap: "peek"|"half"|"full"`, `onSnapChange: (s) => void`, `headerExtra?: ReactNode` (category chips row, always visible), `children: ReactNode` (scrollable list). Exposes the animated translateY so floating controls can anchor (via `onTranslate?: (v: Animated.Value) => void`).

- [ ] **Step 1: Build the component**

Create `mobile/src/features/map/components/MapBottomSheet.tsx`:
```tsx
import { useEffect, useMemo, useRef, type ReactNode } from "react";
import { Animated, Dimensions, PanResponder, View, StyleSheet } from "react-native";
import { colors, radii, spacing } from "@/constants/theme";

type Snap = "peek" | "half" | "full";

interface Props {
  snap: Snap;
  onSnapChange: (s: Snap) => void;
  headerExtra?: ReactNode;
  children: ReactNode;
  onTranslate?: (v: Animated.Value) => void;
}

const H = Dimensions.get("window").height;
// translateY from the top of the sheet container; smaller = taller sheet.
const Y: Record<Snap, number> = { peek: H * 0.88, half: H * 0.42, full: H * 0.08 };

export function MapBottomSheet({ snap, onSnapChange, headerExtra, children, onTranslate }: Props) {
  const y = useRef(new Animated.Value(Y[snap])).current;

  useEffect(() => {
    onTranslate?.(y);
  }, [y, onTranslate]);

  useEffect(() => {
    Animated.spring(y, { toValue: Y[snap], useNativeDriver: true, bounciness: 2 }).start();
  }, [snap, y]);

  const pan = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_e, g) => Math.abs(g.dy) > 6,
        onPanResponderMove: (_e, g) => {
          const next = Y[snap] + g.dy;
          y.setValue(Math.max(Y.full, Math.min(Y.peek, next)));
        },
        onPanResponderRelease: (_e, g) => {
          const landing = Y[snap] + g.dy;
          const nearest = (["full", "half", "peek"] as Snap[]).reduce((best, s) =>
            Math.abs(Y[s] - landing) < Math.abs(Y[best] - landing) ? s : best,
          );
          onSnapChange(nearest);
          Animated.spring(y, { toValue: Y[nearest], useNativeDriver: true, bounciness: 2 }).start();
        },
      }),
    [snap, y, onSnapChange],
  );

  return (
    <Animated.View style={[styles.sheet, { transform: [{ translateY: y }] }]}>
      <View style={styles.handleZone} {...pan.panHandlers}>
        <View style={styles.grabber} />
        {headerExtra}
      </View>
      <View style={styles.body}>{children}</View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    top: 0,
    height: H,
    backgroundColor: colors.bg,
    borderTopLeftRadius: radii.xl,
    borderTopRightRadius: radii.xl,
    shadowColor: "#100E12",
    shadowOpacity: 0.16,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: -4 },
    elevation: 12,
  },
  handleZone: { paddingTop: spacing.sm, paddingBottom: spacing.xs },
  grabber: { alignSelf: "center", width: 40, height: 4, borderRadius: 2, backgroundColor: colors.line, marginBottom: spacing.sm },
  body: { flex: 1 },
});
```

- [ ] **Step 2: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/src/features/map/components/MapBottomSheet.tsx
git commit -m "feat(mobile): 3-snap map bottom sheet (Animated + PanResponder)"
```

---

### Task 12: CategoryChips + NearbyCard components

**Files:**
- Create: `mobile/src/features/map/components/CategoryChips.tsx`
- Create: `mobile/src/features/map/components/NearbyCard.tsx`

> Not unit-tested; gate = lint + typecheck + format + suite green.

**Interfaces:**
- Consumes: `CATEGORY_CHIPS`/`NearbyCategory` (Task 2), `NearbySpot` (`@/lib/api-types`), `formatDistance` (`@/lib/distance`), `RemoteImage`, `Icon`, theme tokens.
- Produces:
  - `CategoryChips({ value, onChange })` — `value: NearbyCategory | null`, single-select horizontal row.
  - `NearbyCard({ spot, selected, onPress })` — list card (image, title, meta pin·subtype·distance, overview first line, congestion chip).

- [ ] **Step 1: Build CategoryChips**

Create `mobile/src/features/map/components/CategoryChips.tsx`:
```tsx
import { ScrollView, Pressable, Text, StyleSheet } from "react-native";
import { CATEGORY_CHIPS, type NearbyCategory } from "@/features/map/lib/nearby-categories";
import { colors, spacing, radii } from "@/constants/theme";

interface Props {
  value: NearbyCategory | null;
  onChange: (v: NearbyCategory | null) => void;
}

export function CategoryChips({ value, onChange }: Props) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.row}
    >
      {CATEGORY_CHIPS.map((chip) => {
        const active = chip.value === value;
        return (
          <Pressable
            key={chip.label}
            onPress={() => onChange(chip.value)}
            style={[styles.chip, active && styles.chipActive]}
          >
            <Text style={[styles.label, active && styles.labelActive]}>{chip.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: { gap: 8, paddingHorizontal: spacing.lg, paddingVertical: spacing.xs },
  chip: { height: 34, paddingHorizontal: 16, borderRadius: radii.pill, alignItems: "center", justifyContent: "center", backgroundColor: colors.fill },
  chipActive: { backgroundColor: colors.ink },
  label: { fontSize: 13.5, fontWeight: "700", color: colors.sec },
  labelActive: { color: colors.onImage },
});
```

- [ ] **Step 2: Build NearbyCard**

Create `mobile/src/features/map/components/NearbyCard.tsx`:
```tsx
import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { formatDistance } from "@/lib/distance";
import type { NearbySpot } from "@/lib/api-types";
import { colors, spacing, radii } from "@/constants/theme";

interface Props {
  spot: NearbySpot;
  selected?: boolean;
  onPress: () => void;
}

const CONGESTION: Record<string, string> = { low: "한산", medium: "보통", high: "붐빔" };

export function NearbyCard({ spot, selected, onPress }: Props) {
  const meta = [spot.sigunguName, spot.category, spot.dist != null ? formatDistance(spot.dist) : null]
    .filter(Boolean)
    .join(" · ");
  const congestion = spot.congestion ? CONGESTION[spot.congestion] : null;

  return (
    <Pressable onPress={onPress} style={[styles.card, selected && styles.selected]}>
      <RemoteImage uri={spot.firstImageUrl} radius={radii.md} style={styles.img} />
      <View style={styles.body}>
        <View style={styles.titleRow}>
          <Text numberOfLines={1} style={styles.title}>
            {spot.title}
          </Text>
          {congestion ? <Text style={styles.congestion}>{congestion}</Text> : null}
        </View>
        {meta ? (
          <View style={styles.metaRow}>
            <Icon name="map-pin" size={13} color={colors.ter} />
            <Text numberOfLines={1} style={styles.meta}>
              {meta}
            </Text>
          </View>
        ) : null}
        {spot.overview ? (
          <Text numberOfLines={1} style={styles.overview}>
            {spot.overview}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { flexDirection: "row", gap: 12, paddingHorizontal: spacing.lg, paddingVertical: spacing.sm },
  selected: { backgroundColor: colors.fill },
  img: { width: 92, height: 92, borderRadius: radii.md, backgroundColor: colors.inset },
  body: { flex: 1, justifyContent: "center", minWidth: 0 },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { flex: 1, fontSize: 16, fontWeight: "700", color: colors.ink },
  congestion: { fontSize: 12, fontWeight: "700", color: colors.sec, backgroundColor: colors.fill, paddingHorizontal: 8, paddingVertical: 2, borderRadius: radii.sm, overflow: "hidden" },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 4 },
  meta: { flex: 1, fontSize: 12.5, color: colors.ter },
  overview: { fontSize: 12.5, color: colors.sec, marginTop: 4 },
});
```

- [ ] **Step 3: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/src/features/map/components/CategoryChips.tsx mobile/src/features/map/components/NearbyCard.tsx
git commit -m "feat(mobile): category chips + nearby list card"
```

---

### Task 13: SearchHerePill + RecenterFab components

**Files:**
- Create: `mobile/src/features/map/components/SearchHerePill.tsx`
- Create: `mobile/src/features/map/components/RecenterFab.tsx`

> Not unit-tested; gate = lint + typecheck + format + suite green.

**Interfaces:**
- Consumes: `Icon`, theme tokens.
- Produces:
  - `SearchHerePill({ onPress })` — floating pill (refresh/search icon + "이 지역에서 검색").
  - `RecenterFab({ onPress })` — floating circular crosshair button.

- [ ] **Step 1: Build SearchHerePill**

Create `mobile/src/features/map/components/SearchHerePill.tsx`:
```tsx
import { Pressable, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, radii, shadows } from "@/constants/theme";

export function SearchHerePill({ onPress }: { onPress: () => void }) {
  return (
    <Pressable style={styles.pill} onPress={onPress}>
      <Icon name="search" size={15} color={colors.ink} />
      <Text style={styles.text}>이 지역에서 검색</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    alignSelf: "center",
    height: 38,
    paddingHorizontal: 16,
    borderRadius: radii.pill,
    backgroundColor: colors.bg,
    ...shadows.fab,
  },
  text: { fontSize: 13.5, fontWeight: "700", color: colors.ink },
});
```

- [ ] **Step 2: Build RecenterFab**

Create `mobile/src/features/map/components/RecenterFab.tsx`:
```tsx
import { Pressable, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, shadows } from "@/constants/theme";

export function RecenterFab({ onPress }: { onPress: () => void }) {
  return (
    <Pressable style={styles.fab} onPress={onPress} hitSlop={8}>
      <Icon name="recenter" size={22} color={colors.ink} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  fab: {
    width: 46,
    height: 46,
    borderRadius: 23,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.bg,
    ...shadows.fab,
  },
});
```

- [ ] **Step 3: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/src/features/map/components/SearchHerePill.tsx mobile/src/features/map/components/RecenterFab.tsx
git commit -m "feat(mobile): search-here pill + recenter FAB"
```

---

### Task 14: PermissionPrimer (04) component

**Files:**
- Create: `mobile/src/features/map/components/PermissionPrimer.tsx`

> Not unit-tested; gate = lint + typecheck + format + suite green + manual smoke.

**Interfaces:**
- Consumes: `Icon`, theme tokens, `Linking`.
- Produces: `PermissionPrimer({ variant, onAllow, onSkip })` — `variant: "priming" | "denied"`. priming: 타이틀/본문 + "위치 허용하기"(onAllow) / "나중에 할게요"(onSkip). denied: + "설정 열기"(`Linking.openSettings`) / "둘러보기"(onSkip). Full-screen overlay covering the map tab (mockup 04).

- [ ] **Step 1: Build the component**

Create `mobile/src/features/map/components/PermissionPrimer.tsx`:
```tsx
import { View, Text, Pressable, Linking, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Icon } from "@/components/Icon";
import { colors, spacing, radii } from "@/constants/theme";

interface Props {
  variant: "priming" | "denied";
  onAllow: () => void;
  onSkip: () => void;
}

const COPY = {
  priming: {
    title: "내 주변 여행지를 보여드릴게요",
    body: "가까운 여행지부터 보여드려요. 위치는 추천에만 쓰고 저장하지 않아요.",
    primary: "위치 허용하기",
    secondary: "나중에 할게요",
  },
  denied: {
    title: "위치가 꺼져 있어요",
    body: "설정에서 위치를 켜면 내 주변 여행지를 추천해 드려요.",
    primary: "설정 열기",
    secondary: "둘러보기",
  },
} as const;

export function PermissionPrimer({ variant, onAllow, onSkip }: Props) {
  const insets = useSafeAreaInsets();
  const c = COPY[variant];
  const onPrimary = variant === "denied" ? () => Linking.openSettings() : onAllow;

  return (
    <View style={[styles.root, { paddingTop: insets.top, paddingBottom: insets.bottom + spacing.xl }]}>
      <View style={styles.body}>
        <View style={[styles.iconCircle, variant === "denied" && styles.iconMuted]}>
          <Icon name="location" size={34} color={variant === "denied" ? colors.ter : colors.ink} />
        </View>
        <Text style={styles.title}>{c.title}</Text>
        <Text style={styles.text}>{c.body}</Text>
      </View>
      <View style={styles.actions}>
        <Pressable style={styles.primary} onPress={onPrimary}>
          <Text style={styles.primaryText}>{c.primary}</Text>
        </Pressable>
        <Pressable style={styles.secondary} onPress={onSkip}>
          <Text style={styles.secondaryText}>{c.secondary}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { ...StyleSheet.absoluteFillObject, backgroundColor: colors.bg, paddingHorizontal: spacing.xl, justifyContent: "space-between" },
  body: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  iconCircle: { width: 84, height: 84, borderRadius: 42, alignItems: "center", justifyContent: "center", backgroundColor: colors.fill, marginBottom: spacing.sm },
  iconMuted: { backgroundColor: colors.inset },
  title: { fontSize: 22, fontWeight: "800", letterSpacing: -0.4, color: colors.ink, textAlign: "center" },
  text: { fontSize: 14, lineHeight: 22, color: colors.sec, textAlign: "center" },
  actions: { gap: spacing.sm },
  primary: { height: 54, borderRadius: radii.md, alignItems: "center", justifyContent: "center", backgroundColor: colors.ink },
  primaryText: { fontSize: 16, fontWeight: "700", color: colors.onImage },
  secondary: { height: 50, alignItems: "center", justifyContent: "center" },
  secondaryText: { fontSize: 15, fontWeight: "600", color: colors.sec },
});
```

- [ ] **Step 2: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/src/features/map/components/PermissionPrimer.tsx
git commit -m "feat(mobile): 04 permission primer/denied overlay"
```

---

### Task 15: RegionPicker (12) modal component

**Files:**
- Create: `mobile/src/features/map/components/RegionPicker.tsx`

> Not unit-tested; gate = lint + typecheck + format + suite green + manual smoke.

**Interfaces:**
- Consumes: `useRegionsTree` (Task 9), `Centroid`/`RegionNode` (`@/lib/api-types`), `Icon`, `Skeleton`, theme tokens, RN `Modal`.
- Produces: `RegionPicker({ visible, onClose, onApply })` — `onApply: (centroid: Centroid, regionName: string) => void`. 2-pane 시도→시군구, `검색` CTA applies the current selection. Row tap = select only.

- [ ] **Step 1: Build the component**

Create `mobile/src/features/map/components/RegionPicker.tsx`:
```tsx
import { useEffect, useState } from "react";
import { Modal, View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Icon } from "@/components/Icon";
import { Skeleton } from "@/components/Skeleton";
import { useRegionsTree } from "@/features/map/queries";
import type { Centroid, RegionNode } from "@/lib/api-types";
import { colors, spacing, radii } from "@/constants/theme";

interface Props {
  visible: boolean;
  onClose: () => void;
  onApply: (centroid: Centroid, regionName: string) => void;
}

export function RegionPicker({ visible, onClose, onApply }: Props) {
  const insets = useSafeAreaInsets();
  const { data: tree, isLoading, isError, refetch } = useRegionsTree();
  const [sidoIdx, setSidoIdx] = useState(0);
  // selection: null = "{시도} 전체", else sigungu index
  const [sigunguIdx, setSigunguIdx] = useState<number | null>(null);

  useEffect(() => {
    if (visible) {
      setSidoIdx(0);
      setSigunguIdx(null);
    }
  }, [visible]);

  const sido: RegionNode | undefined = tree?.[sidoIdx];

  const apply = () => {
    if (!sido) return;
    if (sigunguIdx == null) onApply(sido.centroid, sido.regionName);
    else {
      const sg = sido.sigungus[sigunguIdx];
      onApply(sg.centroid, `${sido.regionName} ${sg.sigunguName}`);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.scrim} onPress={onClose}>
        <Pressable style={[styles.sheet, { paddingBottom: insets.bottom + spacing.md }]} onPress={(e) => e.stopPropagation()}>
          <View style={styles.header}>
            <Pressable style={styles.x} onPress={onClose} hitSlop={8}>
              <Icon name="close" size={22} />
            </Pressable>
            <Text style={styles.title}>지역 선택</Text>
          </View>

          {isError ? (
            <View style={styles.center}>
              <Text style={styles.errText}>지역 목록을 불러오지 못했어요</Text>
              <Pressable style={styles.retry} onPress={() => refetch()}>
                <Text style={styles.retryText}>다시 시도</Text>
              </Pressable>
            </View>
          ) : isLoading || !tree ? (
            <View style={styles.panes}>
              {[0, 1, 2, 3, 4].map((i) => (
                <Skeleton key={i} height={44} style={{ marginBottom: 6 }} />
              ))}
            </View>
          ) : (
            <View style={styles.panes}>
              <ScrollView style={styles.left} showsVerticalScrollIndicator={false}>
                {tree.map((r, i) => (
                  <Pressable
                    key={r.regionCode}
                    style={[styles.sidoRow, i === sidoIdx && styles.sidoActive]}
                    onPress={() => {
                      setSidoIdx(i);
                      setSigunguIdx(null);
                    }}
                  >
                    <Text style={[styles.sidoText, i === sidoIdx && styles.sidoTextActive]}>{r.regionName}</Text>
                  </Pressable>
                ))}
              </ScrollView>
              <ScrollView style={styles.right} showsVerticalScrollIndicator={false}>
                <Pressable style={styles.sgRow} onPress={() => setSigunguIdx(null)}>
                  <Text style={[styles.sgText, sigunguIdx == null && styles.sgActive]}>{sido?.regionName} 전체</Text>
                </Pressable>
                {sido?.sigungus.map((sg, i) => (
                  <Pressable key={sg.sigunguCode} style={styles.sgRow} onPress={() => setSigunguIdx(i)}>
                    <Text style={[styles.sgText, sigunguIdx === i && styles.sgActive]}>{sg.sigunguName}</Text>
                  </Pressable>
                ))}
              </ScrollView>
            </View>
          )}

          <Pressable style={styles.cta} onPress={apply} disabled={!tree}>
            <Text style={styles.ctaText}>검색</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: { flex: 1, justifyContent: "flex-end", backgroundColor: colors.scrim },
  sheet: { height: "62%", backgroundColor: colors.bg, borderTopLeftRadius: radii.xl, borderTopRightRadius: radii.xl },
  header: { height: 52, alignItems: "center", justifyContent: "center", borderBottomWidth: 1, borderBottomColor: colors.line },
  x: { position: "absolute", left: 8, width: 40, height: 40, alignItems: "center", justifyContent: "center" },
  title: { fontSize: 17, fontWeight: "700", color: colors.ink },
  panes: { flex: 1, flexDirection: "row" },
  left: { width: "34%", backgroundColor: colors.inset },
  right: { flex: 1 },
  sidoRow: { paddingVertical: 14, paddingHorizontal: spacing.md },
  sidoActive: { backgroundColor: colors.bg },
  sidoText: { fontSize: 14.5, color: colors.sec },
  sidoTextActive: { color: colors.ink, fontWeight: "700" },
  sgRow: { paddingVertical: 14, paddingHorizontal: spacing.lg },
  sgText: { fontSize: 15, color: colors.sec },
  sgActive: { color: colors.ink, fontWeight: "700" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  errText: { color: colors.sec, fontSize: 14 },
  retry: { paddingHorizontal: 18, height: 38, borderRadius: radii.pill, backgroundColor: colors.fill, alignItems: "center", justifyContent: "center" },
  retryText: { fontSize: 13.5, fontWeight: "700", color: colors.ink },
  cta: { height: 54, margin: spacing.lg, borderRadius: radii.md, alignItems: "center", justifyContent: "center", backgroundColor: colors.ink },
  ctaText: { fontSize: 16, fontWeight: "700", color: colors.onImage },
});
```

- [ ] **Step 2: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/src/features/map/components/RegionPicker.tsx
git commit -m "feat(mobile): 12 region picker modal (2-pane + 검색 CTA)"
```

---

### Task 16: Map screen orchestration (11)

**Files:**
- Modify: `mobile/src/app/(tabs)/map.tsx`

> Not unit-tested; gate = lint + typecheck + format + suite green + manual smoke checklist.

**Interfaces:**
- Consumes: `useMapStore` (Task 8), `useNearbyMap`/`useRegionLabel` (Task 9), `getPermissionStatus`/`requestPermission`/`getCurrentCoords` (Task 7), all map components (Tasks 10-15), `formatHeaderLabel` (Task 4), `SEOUL_CITY_HALL`/`NEARBY_CAP` (`@/constants/map`), `Icon`/`Skeleton`, `router`.

- [ ] **Step 1: Build the screen**

Replace `mobile/src/app/(tabs)/map.tsx` entirely:
```tsx
import { useEffect, useRef, useState } from "react";
import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { Skeleton } from "@/components/Skeleton";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import { MapBottomSheet } from "@/features/map/components/MapBottomSheet";
import { CategoryChips } from "@/features/map/components/CategoryChips";
import { NearbyCard } from "@/features/map/components/NearbyCard";
import { SearchHerePill } from "@/features/map/components/SearchHerePill";
import { RecenterFab } from "@/features/map/components/RecenterFab";
import { PermissionPrimer } from "@/features/map/components/PermissionPrimer";
import { RegionPicker } from "@/features/map/components/RegionPicker";
import { useMapStore } from "@/features/map/stores/map-store";
import { useNearbyMap, useRegionLabel } from "@/features/map/queries";
import { formatHeaderLabel } from "@/features/map/lib/region-label";
import {
  getPermissionStatus,
  requestPermission,
  getCurrentCoords,
  type PermStatus,
} from "@/features/map/usecases/request-location";
import { SEOUL_CITY_HALL, NEARBY_CAP } from "@/constants/map";
import { colors, spacing } from "@/constants/theme";

export default function MapTab() {
  const insets = useSafeAreaInsets();
  const s = useMapStore();
  const [perm, setPerm] = useState<PermStatus | "ready">("undetermined");
  const [pickerOpen, setPickerOpen] = useState(false);
  const started = useRef(false);

  const nearby = useNearbyMap(s.center, s.category);
  const label = useRegionLabel(s.center, s.anchorSource !== "region");
  const spots = (nearby.data ?? []).slice(0, NEARBY_CAP);

  useEffect(() => {
    if (label.data) s.setLabel(label.data);
  }, [label.data]); // eslint-disable-line react-hooks/exhaustive-deps

  // Entry: branch on permission status (S05 §1.4).
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      const status = await getPermissionStatus();
      if (status === "granted") {
        const c = (await getCurrentCoords()) ?? SEOUL_CITY_HALL;
        s.setAnchor(c, "gps", c);
        setPerm("ready");
      } else {
        setPerm(status);
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const allow = async () => {
    const status = await requestPermission();
    if (status === "granted") {
      const c = (await getCurrentCoords()) ?? SEOUL_CITY_HALL;
      s.setAnchor(c, "gps", c);
      setPerm("ready");
    } else {
      setPerm("denied");
    }
  };

  const skipToSeoul = () => {
    s.setAnchor(SEOUL_CITY_HALL, "pan", null);
    setPerm("ready");
  };

  const recenter = async () => {
    if (s.gpsCoords) s.recenterToGps();
    else {
      const status = await getPermissionStatus();
      setPerm(status === "granted" ? "ready" : status);
      if (status === "granted") {
        const c = (await getCurrentCoords()) ?? SEOUL_CITY_HALL;
        s.setAnchor(c, "gps", c);
      }
    }
  };

  if (perm === "undetermined" || perm === "denied") {
    return <PermissionPrimer variant={perm === "denied" ? "denied" : "priming"} onAllow={allow} onSkip={skipToSeoul} />;
  }

  return (
    <View style={styles.root}>
      <KakaoWebMap
        center={s.center}
        pins={spots}
        userLocation={s.gpsCoords}
        onPinTap={(id) => {
          s.selectSpot(id);
          s.setSnap("half");
        }}
        onCenterChanged={(c) => s.onViewportChange(c)}
      />

      <View style={[styles.header, { top: insets.top + spacing.xs }]}>
        <Pressable style={styles.label} onPress={() => setPickerOpen(true)}>
          <Text numberOfLines={1} style={styles.labelText}>
            {formatHeaderLabel(s.anchorSource, s.label)}
          </Text>
          <Icon name="chevron-down" size={18} color={colors.ink} />
        </Pressable>
      </View>

      {s.pillVisible() ? (
        <View style={styles.pill} pointerEvents="box-none">
          <SearchHerePill onPress={() => s.searchHere()} />
        </View>
      ) : null}
      <View style={styles.fab} pointerEvents="box-none">
        <RecenterFab onPress={recenter} />
      </View>

      <MapBottomSheet
        snap={s.snap}
        onSnapChange={s.setSnap}
        headerExtra={<CategoryChips value={s.category} onChange={s.setCategory} />}
      >
        {nearby.isLoading ? (
          <View style={styles.list}>
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} height={92} style={{ marginHorizontal: spacing.lg, marginBottom: spacing.sm }} radius={14} />
            ))}
          </View>
        ) : nearby.isError ? (
          <View style={styles.center}>
            <Text style={styles.dim}>주변 정보를 불러오지 못했어요</Text>
            <Pressable style={styles.retry} onPress={() => nearby.refetch()}>
              <Text style={styles.retryText}>다시 시도</Text>
            </Pressable>
          </View>
        ) : spots.length === 0 ? (
          <View style={styles.center}>
            <Text style={styles.dim}>이 주변엔 아직 추천 스팟이 없어요</Text>
            <Text style={styles.dimSub}>지도를 옮겨 '이 지역에서 검색'을 누르거나, 다른 지역을 선택해 보세요</Text>
          </View>
        ) : (
          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: spacing.xxl }}>
            {spots.map((spot) => (
              <NearbyCard
                key={spot.contentId}
                spot={spot}
                selected={spot.contentId === s.selectedSpotId}
                onPress={() => router.push(`/spots/${spot.contentId}`)}
              />
            ))}
          </ScrollView>
        )}
      </MapBottomSheet>

      <RegionPicker
        visible={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onApply={(centroid, name) => {
          s.applyRegion(centroid);
          s.setLabel({ sido: null, sigungu: null, dong: null, label: name });
          setPickerOpen(false);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: { position: "absolute", left: spacing.lg, right: spacing.lg },
  label: { flexDirection: "row", alignItems: "center", gap: 4, alignSelf: "flex-start", height: 40, paddingHorizontal: 16, borderRadius: 20, backgroundColor: colors.bg, shadowColor: "#100E12", shadowOpacity: 0.12, shadowRadius: 10, shadowOffset: { width: 0, height: 2 }, elevation: 4, maxWidth: "80%" },
  labelText: { fontSize: 15, fontWeight: "700", color: colors.ink },
  pill: { position: "absolute", left: 0, right: 0, bottom: "60%" },
  fab: { position: "absolute", right: spacing.lg, bottom: "60%" },
  list: { paddingTop: spacing.sm },
  center: { alignItems: "center", justifyContent: "center", paddingVertical: spacing.xxl, paddingHorizontal: spacing.xl, gap: spacing.sm },
  dim: { color: colors.sec, fontSize: 15, fontWeight: "600", textAlign: "center" },
  dimSub: { color: colors.ter, fontSize: 13, textAlign: "center", lineHeight: 19 },
  retry: { marginTop: spacing.xs, paddingHorizontal: 18, height: 38, borderRadius: 999, backgroundColor: colors.fill, alignItems: "center", justifyContent: "center" },
  retryText: { fontSize: 13.5, fontWeight: "700", color: colors.ink },
});
```

- [ ] **Step 2: Verify**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green; full suite still passes.

- [ ] **Step 3: Commit**

```bash
git add "mobile/src/app/(tabs)/map.tsx"
git commit -m "feat(mobile): 11 map screen orchestration (webmap + sheet + perm + picker)"
```

---

## Manual smoke checklist (after Task 16)

> Real map render needs a Kakao JS key in `.env` (spec §9). Without it, the map area shows the keyless placeholder; the rest is still exercisable.
- [ ] 지도 탭 진입(권한 미결정) → 04 priming → "나중에 할게요" → 서울 중심 + 리스트(현위치 마커 없음, 라벨 "서울 중구").
- [ ] 권한 허용 → 현위치 중심 + `현위치 · {동}` 라벨 + 현위치 마커.
- [ ] 카테고리 칩 단일선택 → 같은 중심 재조회.
- [ ] 지도 패닝 → "이 지역에서 검색" pill 등장 → 탭 → 중심/리스트 갱신, 라벨 접두사 제거, pill 사라짐.
- [ ] 리센터 FAB(GPS 있음) → 현위치 복귀. (GPS 없음) → 권한 04 재진입.
- [ ] 헤더 라벨 탭 → 지역 피커 → 시도 선택 → 시군구/전체 선택 → 검색 → 지도 재센터 + 라벨 갱신.
- [ ] 바텀시트 peek/half/full 드래그 스냅. 핀 탭 → 시트 half + 카드 하이라이트. 카드 탭 → 스팟 상세.
- [ ] empty(반경 0건) 카피 + error(네트워크) "다시 시도" 동작.

## Self-review notes (coverage vs spec)

- §1 지도(11): KakaoWebMap(T5/T10) · 핀/현위치마커(T5/T10) · 헤더 라벨(T4/T16) · pill(T3/T13/T16) · 리센터(T13/T16) · 3-스냅 시트(T11) · 칩(T2/T12) · 리스트 카드(T12) · 상태 loading/empty/error(T16). ✓
- §2 지역 피커(12): T15 + tree query(T9) + applyRegion(T8). ✓
- 04 권한: T7(usecase) + T14(overlay) + T16(branch). ✓
- §3 데이터: nearby/region/regions-tree(T6). congestion·subtype label·overview from existing NearbySpot. ✓
- §6 스냅/§0 결정: peek/half/full(T11), 거리순 30 cap(NEARBY_CAP, T16), radius 3km(RADIUS_M, T6), 단일선택 칩(T12), 지역 단일선택+검색 CTA(T15). ✓
- 규약: 무채색(파란 현위치 마커 예외), 이모지 0, no `as any`, JSend 1회 언래핑, KakaoWebMap, 새 네이티브 모듈 0. ✓
- 타입 일관성: `LatLng`(T3)→store(T8)/queries(T9)/webmap(T10); `AnchorSource`(T4)→store/label; `NearbyCategory`(T2)→api(T6)/store/chips; `Centroid`/`RegionNode`(T1)→api(T6)/picker(T15)/store applyRegion. ✓
