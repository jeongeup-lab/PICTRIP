# P2 Photo Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the mobile photo-search flow (08 사진 선택 → 09 분석중 → 10 결과 → 07 스팟 상세) as a modal stack launched from the Photo tab.

**Architecture:** A `src/features/photo/` module holds an ephemeral zustand flow store that owns the upload request lifecycle (fired at 08, survives navigation, supports abort/retry), plus pure usecases/libs (image pick, last-known location, similarity bucketing, client sort). Three thin Expo Router screens render store state. The image bytes are uploaded once via `FormData` and never persisted (KTO).

**Tech Stack:** Expo SDK 56 · RN 0.85 · React 19.2 · TypeScript strict · Expo Router (typed routes, modal stack) · zustand · axios · react-native-svg · **new: expo-image-picker** · expo-location (existing) · jest-expo.

## Global Constraints

- Design SSOT: `docs/specs/screens/S04-photo-search.md` (C1–C3 + per-screen). Spec: `docs/superpowers/specs/2026-06-22-mobile-p2-photo-search-design.md`.
- **No emoji. Monochrome tokens only** (`src/constants/theme.ts`); no rose/color. Icons = line-SVG `<Icon>` only.
- **No `as any`.** Use `as unknown as T` where a typed cast is unavoidable (matches `api-client.ts`).
- File naming: components PascalCase; runtime modules (api/lib/stores/usecases/hooks) kebab-case; `src/app/**` follows Expo Router.
- **JSend is unwrapped once** in `api-client`; feature `api.ts` must **not** re-unwrap. UI branches on `err.code` (`AppError`), never `err.message`.
- **KTO compliance (invariant):** uploaded image bytes go only into the single `FormData` upload — never persisted to disk/AsyncStorage/secure-store, never logged. The local asset URI lives only in store memory and is released on flow exit. The result hero uses the **local** asset, never a server URL.
- Similarity is shown as **bucket labels** ("매우 닮음 / 닮음 / 비슷함"), never raw `%`. Distance uses the shared `formatDistance`.
- Location: **never trigger a permission prompt** in this flow — use already-granted last-known position or proceed without distance.
- Verification (run in `mobile/` before declaring any task done): `npm run lint && npm run typecheck && npm run format:check && npm test`.
- Commit per task. **Do not push** unless explicitly asked.

---

### Task 1: Foundation — dependency, config, types, icons

**Files:**
- Modify: `mobile/package.json` (via `expo install`)
- Modify: `mobile/app.json` (plugins)
- Modify: `mobile/src/lib/api-types.ts`
- Modify: `mobile/src/components/Icon.tsx`
- Test: `mobile/src/components/__tests__/Icon.test.tsx` (extend)

**Interfaces:**
- Consumes: existing `SpotCard` interface in `api-types.ts`.
- Produces:
  - `PhotoMatch extends SpotCard { similarity: number; distance?: number | null; regionName?: string | null; sigunguName?: string | null }`
  - `PhotoSearchResult { matches: PhotoMatch[]; queryHadLocation: boolean }`
  - `IconName` additions: `"image"`, `"sparkle"`.

- [ ] **Step 1: Install expo-image-picker**

Run (in `mobile/`):
```bash
npx expo install expo-image-picker
```
Expected: `expo-image-picker` added to `package.json` dependencies.

- [ ] **Step 2: Register the config plugin with Korean usage strings**

Edit `mobile/app.json` — replace the `plugins` array:
```json
    "plugins": [
      "expo-router",
      "expo-secure-store",
      "expo-location",
      [
        "expo-image-picker",
        {
          "photosPermission": "사진 속 분위기로 닮은 여행지를 찾기 위해 사진 보관함에 접근합니다.",
          "cameraPermission": "사진을 촬영해 닮은 여행지를 찾기 위해 카메라에 접근합니다."
        }
      ]
    ],
```

- [ ] **Step 3: Add the photo DTOs to `api-types.ts`**

Append to `mobile/src/lib/api-types.ts` (after the `SpotCard` interface):
```ts
export interface PhotoMatch extends SpotCard {
  similarity: number; // 0..1 (1 - cosine distance)
  distance?: number | null; // metres; present only when query carried lat/lng
  regionName?: string | null;
  sigunguName?: string | null;
}

export interface PhotoSearchResult {
  matches: PhotoMatch[];
  queryHadLocation: boolean;
}
```

- [ ] **Step 4: Add `image` and `sparkle` icons**

In `mobile/src/components/Icon.tsx`, add to the `IconName` union:
```ts
  | "image"
  | "sparkle"
```
Add to the `PATHS` record:
```ts
  image: { d: "M3 5h18v14H3zM3 16l5-5 4 4 3-3 6 6" },
  sparkle: { d: "M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" },
```

- [ ] **Step 5: Extend the Icon render test**

In `mobile/src/components/__tests__/Icon.test.tsx`, add inside the `describe`:
```tsx
  it.each(["image", "sparkle"] as const)("renders %s", async (name) => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<Icon name={name} />);
    });
    expect(r!.toJSON()).toBeTruthy();
  });
```

- [ ] **Step 6: Verify and commit**

Run:
```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green; new Icon cases pass.
```bash
git add mobile/package.json mobile/package-lock.json mobile/app.json mobile/src/lib/api-types.ts mobile/src/components/Icon.tsx mobile/src/components/__tests__/Icon.test.tsx
git commit -m "feat(mobile): P2 foundation — expo-image-picker, photo DTOs, image/sparkle icons"
```

---

### Task 2: Similarity bucket lib

**Files:**
- Create: `mobile/src/features/photo/lib/similarity-bucket.ts`
- Test: `mobile/src/features/photo/lib/__tests__/similarity-bucket.test.ts`

**Interfaces:**
- Produces: `bucketFor(similarity: number): { label: "매우 닮음" | "닮음" | "비슷함"; tier: number }` where `tier ∈ [0,1]` for gauge fill.

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/photo/lib/__tests__/similarity-bucket.test.ts`:
```ts
import { bucketFor } from "@/features/photo/lib/similarity-bucket";

describe("bucketFor", () => {
  it("labels >=0.75 as 매우 닮음 with full tier", () => {
    expect(bucketFor(0.9)).toEqual({ label: "매우 닮음", tier: 1 });
    expect(bucketFor(0.75)).toEqual({ label: "매우 닮음", tier: 1 });
  });
  it("labels >=0.65 and <0.75 as 닮음", () => {
    expect(bucketFor(0.7).label).toBe("닮음");
    expect(bucketFor(0.7).tier).toBeCloseTo(0.66);
  });
  it("labels <0.65 as 비슷함", () => {
    expect(bucketFor(0.5).label).toBe("비슷함");
    expect(bucketFor(0.5).tier).toBeCloseTo(0.33);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/photo/lib/__tests__/similarity-bucket.test.ts`
Expected: FAIL — cannot find module `similarity-bucket`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/photo/lib/similarity-bucket.ts`:
```ts
/** Map raw CLIP similarity (0..1) to an honest bucket label + gauge tier.
 * Raw cosine reads deceptively low (S11 §2) so we never show the number.
 * Thresholds are tunable; calibrate against labelled pairs later. */
export type SimilarityLabel = "매우 닮음" | "닮음" | "비슷함";

export interface SimilarityBucket {
  label: SimilarityLabel;
  tier: number; // gauge fill fraction 0..1
}

export function bucketFor(similarity: number): SimilarityBucket {
  if (similarity >= 0.75) return { label: "매우 닮음", tier: 1 };
  if (similarity >= 0.65) return { label: "닮음", tier: 0.66 };
  return { label: "비슷함", tier: 0.33 };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/photo/lib/__tests__/similarity-bucket.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/photo/lib/similarity-bucket.ts mobile/src/features/photo/lib/__tests__/similarity-bucket.test.ts
git commit -m "feat(mobile): similarity bucket label/tier mapping"
```

---

### Task 3: Sort matches lib

**Files:**
- Create: `mobile/src/features/photo/lib/sort-matches.ts`
- Test: `mobile/src/features/photo/lib/__tests__/sort-matches.test.ts`

**Interfaces:**
- Consumes: `PhotoMatch` from `@/lib/api-types` (Task 1).
- Produces: `type SortMode = "similarity" | "distance"`; `sortMatches(matches: PhotoMatch[], mode: SortMode): PhotoMatch[]` (returns a new array; `similarity` = desc; `distance` = asc with similarity-desc tiebreak, nulls last).

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/photo/lib/__tests__/sort-matches.test.ts`:
```ts
import { sortMatches } from "@/features/photo/lib/sort-matches";
import type { PhotoMatch } from "@/lib/api-types";

const m = (contentId: string, similarity: number, distance: number | null): PhotoMatch => ({
  contentId,
  title: contentId,
  firstImageUrl: null,
  category: null,
  similarity,
  distance,
});

describe("sortMatches", () => {
  const data = [m("a", 0.7, 5000), m("b", 0.9, 12000), m("c", 0.8, null)];

  it("similarity sorts by similarity desc", () => {
    expect(sortMatches(data, "similarity").map((x) => x.contentId)).toEqual(["b", "c", "a"]);
  });
  it("distance sorts asc with nulls last", () => {
    expect(sortMatches(data, "distance").map((x) => x.contentId)).toEqual(["a", "b", "c"]);
  });
  it("distance ties break by similarity desc", () => {
    const tie = [m("x", 0.6, 1000), m("y", 0.95, 1000)];
    expect(sortMatches(tie, "distance").map((x) => x.contentId)).toEqual(["y", "x"]);
  });
  it("does not mutate the input", () => {
    const input = [...data];
    sortMatches(input, "similarity");
    expect(input.map((x) => x.contentId)).toEqual(["a", "b", "c"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/photo/lib/__tests__/sort-matches.test.ts`
Expected: FAIL — cannot find module `sort-matches`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/photo/lib/sort-matches.ts`:
```ts
import type { PhotoMatch } from "@/lib/api-types";

export type SortMode = "similarity" | "distance";

/** Client-side re-sort of server matches (no refetch). distance asc with a
 * similarity-desc tiebreak; matches without distance sink to the bottom. */
export function sortMatches(matches: PhotoMatch[], mode: SortMode): PhotoMatch[] {
  const copy = [...matches];
  if (mode === "distance") {
    copy.sort((a, b) => {
      const ad = a.distance ?? Infinity;
      const bd = b.distance ?? Infinity;
      if (ad !== bd) return ad - bd;
      return b.similarity - a.similarity;
    });
  } else {
    copy.sort((a, b) => b.similarity - a.similarity);
  }
  return copy;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/photo/lib/__tests__/sort-matches.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/photo/lib/sort-matches.ts mobile/src/features/photo/lib/__tests__/sort-matches.test.ts
git commit -m "feat(mobile): client-side match sorting (similarity/distance)"
```

---

### Task 4: Last-known location usecase

**Files:**
- Create: `mobile/src/features/photo/usecases/get-last-known-coords.ts`
- Test: `mobile/src/features/photo/usecases/__tests__/get-last-known-coords.test.ts`

**Interfaces:**
- Produces: `interface Coords { lat: number; lng: number }`; `getLastKnownCoords(): Promise<Coords | null>`. Returns null when permission not already granted or no last-known fix. **Never requests permission.**

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/photo/usecases/__tests__/get-last-known-coords.test.ts`:
```ts
jest.mock("expo-location", () => ({
  getForegroundPermissionsAsync: jest.fn(),
  getLastKnownPositionAsync: jest.fn(),
}));

import * as Location from "expo-location";
import { getLastKnownCoords } from "@/features/photo/usecases/get-last-known-coords";

describe("getLastKnownCoords", () => {
  beforeEach(() => jest.clearAllMocks());

  it("returns null and never reads position when permission not granted", async () => {
    (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ granted: false });
    expect(await getLastKnownCoords()).toBeNull();
    expect(Location.getLastKnownPositionAsync).not.toHaveBeenCalled();
  });

  it("returns null when granted but no last-known fix", async () => {
    (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ granted: true });
    (Location.getLastKnownPositionAsync as jest.Mock).mockResolvedValue(null);
    expect(await getLastKnownCoords()).toBeNull();
  });

  it("returns coords when granted and a fix exists", async () => {
    (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ granted: true });
    (Location.getLastKnownPositionAsync as jest.Mock).mockResolvedValue({
      coords: { latitude: 37.5, longitude: 127.0 },
    });
    expect(await getLastKnownCoords()).toEqual({ lat: 37.5, lng: 127.0 });
  });
});
```

> Note: the mock deliberately omits `requestForegroundPermissionsAsync`. If the implementation ever calls it, the test throws — enforcing the no-prompt invariant.

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/photo/usecases/__tests__/get-last-known-coords.test.ts`
Expected: FAIL — cannot find module `get-last-known-coords`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/photo/usecases/get-last-known-coords.ts`:
```ts
import * as Location from "expo-location";

export interface Coords {
  lat: number;
  lng: number;
}

/** Read an already-granted last-known position. NEVER requests permission
 * (S04: photo search must not trigger a location prompt). Returns null when
 * permission is not granted or there is no cached fix. */
export async function getLastKnownCoords(): Promise<Coords | null> {
  const perm = await Location.getForegroundPermissionsAsync();
  if (!perm.granted) return null;
  const pos = await Location.getLastKnownPositionAsync();
  if (!pos) return null;
  return { lat: pos.coords.latitude, lng: pos.coords.longitude };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/photo/usecases/__tests__/get-last-known-coords.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/photo/usecases/get-last-known-coords.ts mobile/src/features/photo/usecases/__tests__/get-last-known-coords.test.ts
git commit -m "feat(mobile): last-known coords usecase (no permission prompt)"
```

---

### Task 5: Image pick usecase

**Files:**
- Create: `mobile/src/features/photo/usecases/pick-image.ts`
- Test: `mobile/src/features/photo/usecases/__tests__/pick-image.test.ts`

**Interfaces:**
- Produces:
  - `interface PickedImage { uri: string; mimeType: string; fileName: string }`
  - `type PickResult = PickedImage | "canceled" | "permission-denied"`
  - `pickFromLibrary(): Promise<PickResult>` (system picker, no permission prompt)
  - `captureFromCamera(): Promise<PickResult>` (just-in-time camera permission)

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/photo/usecases/__tests__/pick-image.test.ts`:
```ts
jest.mock("expo-image-picker", () => ({
  launchImageLibraryAsync: jest.fn(),
  launchCameraAsync: jest.fn(),
  requestCameraPermissionsAsync: jest.fn(),
}));

import * as ImagePicker from "expo-image-picker";
import { pickFromLibrary, captureFromCamera } from "@/features/photo/usecases/pick-image";

const asset = { uri: "file:///a.jpg", mimeType: "image/png", fileName: "a.png" };

describe("pick-image", () => {
  beforeEach(() => jest.clearAllMocks());

  it("library pick maps the first asset and never requests camera permission", async () => {
    (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValue({
      canceled: false,
      assets: [asset],
    });
    expect(await pickFromLibrary()).toEqual({
      uri: "file:///a.jpg",
      mimeType: "image/png",
      fileName: "a.png",
    });
    expect(ImagePicker.requestCameraPermissionsAsync).not.toHaveBeenCalled();
  });

  it("library cancel returns 'canceled'", async () => {
    (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValue({
      canceled: true,
      assets: null,
    });
    expect(await pickFromLibrary()).toBe("canceled");
  });

  it("camera requests permission and returns 'permission-denied' when refused", async () => {
    (ImagePicker.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({ granted: false });
    expect(await captureFromCamera()).toBe("permission-denied");
    expect(ImagePicker.launchCameraAsync).not.toHaveBeenCalled();
  });

  it("camera captures when granted", async () => {
    (ImagePicker.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({ granted: true });
    (ImagePicker.launchCameraAsync as jest.Mock).mockResolvedValue({ canceled: false, assets: [asset] });
    expect(await captureFromCamera()).toEqual({
      uri: "file:///a.jpg",
      mimeType: "image/png",
      fileName: "a.png",
    });
  });

  it("falls back to defaults when asset omits mime/name", async () => {
    (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValue({
      canceled: false,
      assets: [{ uri: "file:///b" }],
    });
    expect(await pickFromLibrary()).toEqual({
      uri: "file:///b",
      mimeType: "image/jpeg",
      fileName: "photo.jpg",
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/photo/usecases/__tests__/pick-image.test.ts`
Expected: FAIL — cannot find module `pick-image`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/photo/usecases/pick-image.ts`:
```ts
import * as ImagePicker from "expo-image-picker";

export interface PickedImage {
  uri: string;
  mimeType: string;
  fileName: string;
}

export type PickResult = PickedImage | "canceled" | "permission-denied";

function toPicked(result: ImagePicker.ImagePickerResult): PickResult {
  if (result.canceled || !result.assets || !result.assets[0]) return "canceled";
  const a = result.assets[0];
  return {
    uri: a.uri,
    mimeType: a.mimeType ?? "image/jpeg",
    fileName: a.fileName ?? "photo.jpg",
  };
}

/** System photo picker — no permission prompt (iOS PHPicker / Android Photo Picker). */
export async function pickFromLibrary(): Promise<PickResult> {
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ["images"],
    allowsMultipleSelection: false,
    quality: 0.8,
  });
  return toPicked(result);
}

/** Camera capture — requests camera permission just-in-time. */
export async function captureFromCamera(): Promise<PickResult> {
  const perm = await ImagePicker.requestCameraPermissionsAsync();
  if (!perm.granted) return "permission-denied";
  const result = await ImagePicker.launchCameraAsync({ quality: 0.8 });
  return toPicked(result);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/photo/usecases/__tests__/pick-image.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/photo/usecases/pick-image.ts mobile/src/features/photo/usecases/__tests__/pick-image.test.ts
git commit -m "feat(mobile): image pick usecase (library + camera)"
```

---

### Task 6: Photo-search API

**Files:**
- Create: `mobile/src/features/photo/api.ts`
- Test: `mobile/src/features/photo/__tests__/api.test.ts`

**Interfaces:**
- Consumes: `api` from `@/lib/api-client`; `PickedImage` (Task 5); `Coords` (Task 4); `PhotoSearchResult` (Task 1).
- Produces: `photoSearch(asset: PickedImage, coords: Coords | null, signal?: AbortSignal): Promise<PhotoSearchResult>`.

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/photo/__tests__/api.test.ts`:
```ts
jest.mock("@/lib/api-client", () => ({ api: { post: jest.fn() } }));

import { api } from "@/lib/api-client";
import { photoSearch } from "@/features/photo/api";

const asset = { uri: "file:///x.jpg", mimeType: "image/jpeg", fileName: "x.jpg" };

describe("photoSearch", () => {
  beforeEach(() => jest.clearAllMocks());

  it("posts multipart FormData with lat/lng params when coords given", async () => {
    (api.post as jest.Mock).mockResolvedValue({ matches: [], queryHadLocation: true });
    const res = await photoSearch(asset, { lat: 1, lng: 2 });
    expect(api.post).toHaveBeenCalledWith(
      "/taste/photo-search",
      expect.any(FormData),
      expect.objectContaining({ params: { lat: 1, lng: 2 } }),
    );
    expect(res.queryHadLocation).toBe(true);
  });

  it("omits params when coords is null and forwards the abort signal", async () => {
    (api.post as jest.Mock).mockResolvedValue({ matches: [], queryHadLocation: false });
    const controller = new AbortController();
    await photoSearch(asset, null, controller.signal);
    expect(api.post).toHaveBeenCalledWith(
      "/taste/photo-search",
      expect.any(FormData),
      expect.objectContaining({ params: undefined, signal: controller.signal }),
    );
  });

  it("returns the unwrapped result without re-unwrapping", async () => {
    const payload = { matches: [{ contentId: "1" }], queryHadLocation: false };
    (api.post as jest.Mock).mockResolvedValue(payload);
    expect(await photoSearch(asset, null)).toBe(payload);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/photo/__tests__/api.test.ts`
Expected: FAIL — cannot find module `api`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/photo/api.ts`:
```ts
import { api } from "@/lib/api-client";
import type { PhotoSearchResult } from "@/lib/api-types";
import type { PickedImage } from "@/features/photo/usecases/pick-image";
import type { Coords } from "@/features/photo/usecases/get-last-known-coords";

/** POST the photo as multipart/form-data. api-client already unwraps JSend, so
 * the result is returned as-is (no re-unwrap). The image bytes are uploaded
 * once and never persisted (KTO). RN sets the multipart boundary itself. */
export async function photoSearch(
  asset: PickedImage,
  coords: Coords | null,
  signal?: AbortSignal,
): Promise<PhotoSearchResult> {
  const form = new FormData();
  const filePart = { uri: asset.uri, name: asset.fileName, type: asset.mimeType };
  form.append("image", filePart as unknown as Blob);
  return (await api.post("/taste/photo-search", form, {
    params: coords ? { lat: coords.lat, lng: coords.lng } : undefined,
    headers: { "Content-Type": "multipart/form-data" },
    signal,
  })) as unknown as PhotoSearchResult;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/photo/__tests__/api.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/photo/api.ts mobile/src/features/photo/__tests__/api.test.ts
git commit -m "feat(mobile): photo-search multipart API call"
```

---

### Task 7: Photo flow store

**Files:**
- Create: `mobile/src/features/photo/stores/photo-flow-store.ts`
- Test: `mobile/src/features/photo/stores/__tests__/photo-flow-store.test.ts`

**Interfaces:**
- Consumes: `photoSearch` (Task 6); `getLastKnownCoords` (Task 4); `PickedImage` (Task 5); `PhotoSearchResult` (Task 1); `AppError`/`ErrorCode` from `@/lib/app-error`.
- Produces: `usePhotoFlowStore` (zustand) with state `{ asset, status: "idle"|"loading"|"success"|"error", result, errorCode, controller }` and actions `setAsset(asset)`, `clearAsset()`, `startSearch(): Promise<void>`, `abort()`, `reset()`.

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/photo/stores/__tests__/photo-flow-store.test.ts`:
```ts
jest.mock("@/features/photo/api", () => ({ photoSearch: jest.fn() }));
jest.mock("@/features/photo/usecases/get-last-known-coords", () => ({
  getLastKnownCoords: jest.fn(),
}));

import { usePhotoFlowStore } from "@/features/photo/stores/photo-flow-store";
import { photoSearch } from "@/features/photo/api";
import { getLastKnownCoords } from "@/features/photo/usecases/get-last-known-coords";
import { AppError } from "@/lib/app-error";

const asset = { uri: "file:///x.jpg", mimeType: "image/jpeg", fileName: "x.jpg" };

describe("photo-flow-store", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    usePhotoFlowStore.getState().reset();
    (getLastKnownCoords as jest.Mock).mockResolvedValue(null);
  });

  it("startSearch transitions loading → success and stores the result", async () => {
    const result = { matches: [], queryHadLocation: false };
    (photoSearch as jest.Mock).mockResolvedValue(result);
    usePhotoFlowStore.getState().setAsset(asset);
    await usePhotoFlowStore.getState().startSearch();
    expect(usePhotoFlowStore.getState().status).toBe("success");
    expect(usePhotoFlowStore.getState().result).toBe(result);
  });

  it("startSearch sets error + errorCode on AppError", async () => {
    (photoSearch as jest.Mock).mockRejectedValue(new AppError("IMAGE_INVALID", "x", 400));
    usePhotoFlowStore.getState().setAsset(asset);
    await usePhotoFlowStore.getState().startSearch();
    expect(usePhotoFlowStore.getState().status).toBe("error");
    expect(usePhotoFlowStore.getState().errorCode).toBe("IMAGE_INVALID");
  });

  it("startSearch is a no-op without an asset", async () => {
    await usePhotoFlowStore.getState().startSearch();
    expect(photoSearch).not.toHaveBeenCalled();
    expect(usePhotoFlowStore.getState().status).toBe("idle");
  });

  it("abort sets status idle and clears the controller", async () => {
    usePhotoFlowStore.getState().setAsset(asset);
    usePhotoFlowStore.getState().abort();
    expect(usePhotoFlowStore.getState().status).toBe("idle");
    expect(usePhotoFlowStore.getState().controller).toBeNull();
  });

  it("reset releases asset and result", async () => {
    usePhotoFlowStore.getState().setAsset(asset);
    usePhotoFlowStore.setState({ result: { matches: [], queryHadLocation: false }, status: "success" });
    usePhotoFlowStore.getState().reset();
    const s = usePhotoFlowStore.getState();
    expect(s.asset).toBeNull();
    expect(s.result).toBeNull();
    expect(s.status).toBe("idle");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/photo/stores/__tests__/photo-flow-store.test.ts`
Expected: FAIL — cannot find module `photo-flow-store`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/photo/stores/photo-flow-store.ts`:
```ts
import { create } from "zustand";
import { AppError, type ErrorCode } from "@/lib/app-error";
import type { PhotoSearchResult } from "@/lib/api-types";
import type { PickedImage } from "@/features/photo/usecases/pick-image";
import { getLastKnownCoords } from "@/features/photo/usecases/get-last-known-coords";
import { photoSearch } from "@/features/photo/api";

type Status = "idle" | "loading" | "success" | "error";

interface PhotoFlowState {
  asset: PickedImage | null;
  status: Status;
  result: PhotoSearchResult | null;
  errorCode: ErrorCode | null;
  controller: AbortController | null;
  setAsset: (asset: PickedImage) => void;
  clearAsset: () => void;
  startSearch: () => Promise<void>;
  abort: () => void;
  reset: () => void;
}

/** Ephemeral flow state. NOT TanStack — results are non-cacheable and the image
 * lives only in memory, released on reset() (KTO). Owns the request lifecycle so
 * it survives the 08→09 navigation and supports abort/retry from 09. */
export const usePhotoFlowStore = create<PhotoFlowState>((set, get) => ({
  asset: null,
  status: "idle",
  result: null,
  errorCode: null,
  controller: null,

  setAsset: (asset) => set({ asset }),
  clearAsset: () => set({ asset: null }),

  startSearch: async () => {
    const { asset } = get();
    if (!asset) return;
    get().controller?.abort();
    const controller = new AbortController();
    set({ status: "loading", result: null, errorCode: null, controller });
    try {
      const coords = await getLastKnownCoords();
      const result = await photoSearch(asset, coords, controller.signal);
      if (controller.signal.aborted) return;
      set({ status: "success", result, controller: null });
    } catch (e) {
      if (controller.signal.aborted) return;
      set({ status: "error", errorCode: e instanceof AppError ? e.code : "UNKNOWN", controller: null });
    }
  },

  abort: () => {
    get().controller?.abort();
    set({ status: "idle", controller: null });
  },

  reset: () =>
    set({ asset: null, status: "idle", result: null, errorCode: null, controller: null }),
}));
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/photo/stores/__tests__/photo-flow-store.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/photo/stores/photo-flow-store.ts mobile/src/features/photo/stores/__tests__/photo-flow-store.test.ts
git commit -m "feat(mobile): ephemeral photo flow store (request lifecycle + abort)"
```

---

### Task 8: SimilarityGauge component

**Files:**
- Create: `mobile/src/features/photo/components/SimilarityGauge.tsx`
- Test: `mobile/src/features/photo/components/__tests__/SimilarityGauge.test.tsx`

**Interfaces:**
- Consumes: `bucketFor` (Task 2); `colors` from `@/constants/theme`; `react-native-svg`.
- Produces: `SimilarityGauge({ similarity, size? }: { similarity: number; size?: number })` — a ring filled to the bucket tier (no number) + the bucket label text.

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/photo/components/__tests__/SimilarityGauge.test.tsx`:
```tsx
import renderer, { act } from "react-test-renderer";
import { SimilarityGauge } from "@/features/photo/components/SimilarityGauge";

async function render(el: React.ReactElement) {
  let r: renderer.ReactTestRenderer;
  await act(async () => {
    r = renderer.create(el);
  });
  return r!;
}

describe("SimilarityGauge", () => {
  it("shows the bucket label for a high similarity", async () => {
    const r = await render(<SimilarityGauge similarity={0.92} />);
    expect(JSON.stringify(r.toJSON())).toContain("매우 닮음");
  });
  it("shows 비슷함 for a low similarity", async () => {
    const r = await render(<SimilarityGauge similarity={0.4} />);
    expect(JSON.stringify(r.toJSON())).toContain("비슷함");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/photo/components/__tests__/SimilarityGauge.test.tsx`
Expected: FAIL — cannot find module `SimilarityGauge`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/photo/components/SimilarityGauge.tsx`:
```tsx
import { View, Text, StyleSheet } from "react-native";
import Svg, { Circle } from "react-native-svg";
import { bucketFor } from "@/features/photo/lib/similarity-bucket";
import { colors } from "@/constants/theme";

interface Props {
  similarity: number;
  size?: number;
}

/** Circular ring filled to the bucket tier (no raw %), plus the bucket label.
 * Rendered on the dark glass result bar — stroke/text are on-image white. */
export function SimilarityGauge({ similarity, size = 44 }: Props) {
  const { label, tier } = bucketFor(similarity);
  const stroke = 3;
  const r = size / 2 - stroke;
  const circumference = 2 * Math.PI * r;
  return (
    <View style={styles.wrap}>
      <Svg width={size} height={size}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={colors.glassBorder} strokeWidth={stroke} fill="none" />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={colors.onImage}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - tier)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </Svg>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: "center", gap: 3, flexShrink: 0 },
  label: { fontSize: 11, fontWeight: "700", color: colors.onImage },
});
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/photo/components/__tests__/SimilarityGauge.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/photo/components/SimilarityGauge.tsx mobile/src/features/photo/components/__tests__/SimilarityGauge.test.tsx
git commit -m "feat(mobile): SimilarityGauge (bucket ring + label, no raw %)"
```

---

### Task 9: ResultCard component

**Files:**
- Create: `mobile/src/features/photo/components/ResultCard.tsx`
- Test: `mobile/src/features/photo/components/__tests__/ResultCard.test.tsx`

**Interfaces:**
- Consumes: `RemoteImage` from `@/components/RemoteImage`; `SimilarityGauge` (Task 8); `formatDistance` from `@/lib/distance`; `PhotoMatch` (Task 1); theme tokens.
- Produces: `ResultCard({ match, showDistance, onPress }: { match: PhotoMatch; showDistance: boolean; onPress: () => void })`.

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/photo/components/__tests__/ResultCard.test.tsx`:
```tsx
import renderer, { act } from "react-test-renderer";
import { ResultCard } from "@/features/photo/components/ResultCard";
import type { PhotoMatch } from "@/lib/api-types";

const base: PhotoMatch = {
  contentId: "1",
  title: "곽지해수욕장",
  firstImageUrl: null,
  category: "해변",
  similarity: 0.96,
  distance: 3400,
  regionName: "제주",
  sigunguName: "제주시",
};

async function render(el: React.ReactElement) {
  let r: renderer.ReactTestRenderer;
  await act(async () => {
    r = renderer.create(el);
  });
  return JSON.stringify(r!.toJSON());
}

describe("ResultCard", () => {
  it("shows name, category·region, distance and bucket label when showDistance", async () => {
    const tree = await render(<ResultCard match={base} showDistance onPress={() => {}} />);
    expect(tree).toContain("곽지해수욕장");
    expect(tree).toContain("해변 · 제주 제주시 · 3.4km");
    expect(tree).toContain("매우 닮음");
  });
  it("omits distance when showDistance is false", async () => {
    const tree = await render(<ResultCard match={base} showDistance={false} onPress={() => {}} />);
    expect(tree).toContain("해변 · 제주 제주시");
    expect(tree).not.toContain("3.4km");
  });
  it("omits distance when distance is null even if showDistance", async () => {
    const tree = await render(
      <ResultCard match={{ ...base, distance: null }} showDistance onPress={() => {}} />,
    );
    expect(tree).not.toContain("km");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/photo/components/__tests__/ResultCard.test.tsx`
Expected: FAIL — cannot find module `ResultCard`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/photo/components/ResultCard.tsx`:
```tsx
import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { SimilarityGauge } from "@/features/photo/components/SimilarityGauge";
import { formatDistance } from "@/lib/distance";
import type { PhotoMatch } from "@/lib/api-types";
import { colors, radii } from "@/constants/theme";

interface Props {
  match: PhotoMatch;
  showDistance: boolean;
  onPress: () => void;
}

export function ResultCard({ match, showDistance, onPress }: Props) {
  const region = [match.regionName, match.sigunguName].filter(Boolean).join(" ");
  const parts: string[] = [];
  if (match.category) parts.push(match.category);
  if (region) parts.push(region);
  if (showDistance && match.distance != null) parts.push(formatDistance(match.distance));
  const meta = parts.join(" · ");

  return (
    <Pressable onPress={onPress} style={styles.card}>
      <RemoteImage uri={match.firstImageUrl} radius={radii.xl} style={styles.image} />
      <View style={styles.bar}>
        <View style={styles.tx}>
          <Text numberOfLines={1} style={styles.name}>
            {match.title}
          </Text>
          {meta ? (
            <Text numberOfLines={1} style={styles.meta}>
              {meta}
            </Text>
          ) : null}
        </View>
        <SimilarityGauge similarity={match.similarity} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { height: 188, borderRadius: radii.xl, overflow: "hidden", backgroundColor: colors.inset },
  image: { width: "100%", height: "100%" },
  bar: {
    position: "absolute",
    left: 12,
    right: 12,
    bottom: 12,
    borderRadius: 15,
    paddingHorizontal: 16,
    paddingVertical: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    backgroundColor: colors.scrim,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  tx: { flex: 1, minWidth: 0 },
  name: { fontSize: 17, fontWeight: "700", color: colors.onImage },
  meta: { fontSize: 12.5, color: colors.onDim, marginTop: 2 },
});
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/photo/components/__tests__/ResultCard.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/photo/components/ResultCard.tsx mobile/src/features/photo/components/__tests__/ResultCard.test.tsx
git commit -m "feat(mobile): ResultCard (glass bar, conditional distance, gauge)"
```

---

### Task 10: Navigation wiring + 08 select screen

**Files:**
- Create: `mobile/src/app/photo/_layout.tsx`
- Create: `mobile/src/app/photo/select.tsx`
- Modify: `mobile/src/app/_layout.tsx`
- Modify: `mobile/src/app/(tabs)/_layout.tsx`

**Interfaces:**
- Consumes: `usePhotoFlowStore` (Task 7); `pickFromLibrary`/`captureFromCamera` (Task 5); `Icon`, theme tokens.
- Produces: route `/photo/select` (08); the Photo tab launches it.

> Screens are not unit-tested in this project (Expo Router needs heavy router mocks); the gate is lint + typecheck + format + the full suite staying green, plus the manual checklist at the end.

- [ ] **Step 1: Create the photo stack layout**

Create `mobile/src/app/photo/_layout.tsx`:
```tsx
import { Stack } from "expo-router";

export default function PhotoLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
```

- [ ] **Step 2: Register the photo group as a modal in the root layout**

In `mobile/src/app/_layout.tsx`, add inside the root `<Stack>` (after the `spots/[contentId]` screen):
```tsx
          <Stack.Screen name="photo" options={{ presentation: "modal" }} />
```

- [ ] **Step 3: Intercept the Photo tab press**

In `mobile/src/app/(tabs)/_layout.tsx`, add the router import at the top:
```tsx
import { Tabs, router } from "expo-router";
```
(remove the separate `import { Tabs } from "expo-router";`).

Replace the photo `Tabs.Screen` with:
```tsx
      <Tabs.Screen
        name="photo"
        options={{ title: "사진", tabBarIcon: tabIcon("camera") }}
        listeners={{
          tabPress: (e) => {
            e.preventDefault();
            router.push("/photo/select");
          },
        }}
      />
```

- [ ] **Step 4: Build the 08 select screen**

Create `mobile/src/app/photo/select.tsx`:
```tsx
import { useEffect, useState } from "react";
import { View, Text, Pressable, Image, Linking, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { usePhotoFlowStore } from "@/features/photo/stores/photo-flow-store";
import { pickFromLibrary, captureFromCamera, type PickResult } from "@/features/photo/usecases/pick-image";
import { colors, spacing, radii } from "@/constants/theme";

export default function PhotoSelectScreen() {
  const insets = useSafeAreaInsets();
  const asset = usePhotoFlowStore((s) => s.asset);
  const setAsset = usePhotoFlowStore((s) => s.setAsset);
  const clearAsset = usePhotoFlowStore((s) => s.clearAsset);
  const startSearch = usePhotoFlowStore((s) => s.startSearch);
  const reset = usePhotoFlowStore((s) => s.reset);
  const [cameraDenied, setCameraDenied] = useState(false);

  // 08 is the root of the photo stack — it unmounts exactly when the flow ends
  // (modal dismissed or replaced into spot detail). Release the image then (KTO).
  useEffect(() => () => reset(), [reset]);

  const handle = (result: PickResult) => {
    if (result === "permission-denied") {
      setCameraDenied(true);
      return;
    }
    if (result === "canceled") return;
    setCameraDenied(false);
    setAsset(result);
  };

  const analyze = () => {
    if (!asset) return;
    startSearch();
    router.push("/photo/analyzing");
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.sm }]}>
      <Pressable style={styles.back} onPress={() => router.back()} hitSlop={8}>
        <Icon name="chevron-left" size={23} />
      </Pressable>

      <View style={styles.body}>
        <Text style={styles.title}>사진 속 분위기로{"\n"}여행지를 찾아요</Text>
        <Text style={styles.sub}>마음에 드는 사진 한 장이면 충분해요.</Text>

        <View style={styles.preview}>
          {asset ? (
            <>
              <Image source={{ uri: asset.uri }} style={styles.previewImg} />
              <Pressable style={styles.remove} onPress={clearAsset} hitSlop={8}>
                <Icon name="close" size={18} color={colors.onImage} />
              </Pressable>
            </>
          ) : (
            <View style={styles.placeholder}>
              <Text style={styles.placeholderText}>사진을 고르세요</Text>
            </View>
          )}
        </View>

        {cameraDenied ? (
          <Pressable onPress={() => Linking.openSettings()}>
            <Text style={styles.denied}>설정에서 카메라 권한을 켜 주세요</Text>
          </Pressable>
        ) : null}

        <View style={styles.actions}>
          <Pressable style={styles.btn} onPress={async () => handle(await captureFromCamera())}>
            <Icon name="camera" size={20} />
            <Text style={styles.btnText}>촬영</Text>
          </Pressable>
          <Pressable style={styles.btn} onPress={async () => handle(await pickFromLibrary())}>
            <Icon name="image" size={20} />
            <Text style={styles.btnText}>갤러리</Text>
          </Pressable>
        </View>

        <Pressable
          style={[styles.cta, !asset && styles.ctaDisabled]}
          onPress={analyze}
          disabled={!asset}
        >
          <Icon name="sparkle" size={19} color={colors.onImage} />
          <Text style={styles.ctaText}>분석하기</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  back: { width: 40, height: 40, alignItems: "center", justifyContent: "center", marginLeft: spacing.xs },
  body: { flex: 1, paddingHorizontal: spacing.xl, paddingBottom: spacing.lg },
  title: { fontSize: 25, fontWeight: "700", letterSpacing: -0.55, lineHeight: 32, color: colors.ink },
  sub: { color: colors.sec, fontSize: 14, marginTop: 8 },
  preview: { flex: 1, marginVertical: spacing.md, borderRadius: radii.xl, overflow: "hidden", backgroundColor: colors.inset },
  previewImg: { width: "100%", height: "100%" },
  placeholder: { flex: 1, alignItems: "center", justifyContent: "center", borderWidth: 1.5, borderColor: colors.line, borderStyle: "dashed", borderRadius: radii.xl },
  placeholderText: { color: colors.ter, fontSize: 15, fontWeight: "600" },
  remove: { position: "absolute", top: 12, right: 12, width: 34, height: 34, borderRadius: 17, backgroundColor: colors.control, alignItems: "center", justifyContent: "center" },
  denied: { color: colors.sec, fontSize: 13, marginBottom: spacing.sm, textDecorationLine: "underline" },
  actions: { flexDirection: "row", gap: 11, marginBottom: 11 },
  btn: { flex: 1, height: 54, borderRadius: radii.sm, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, backgroundColor: colors.inset },
  btnText: { fontSize: 15, fontWeight: "700", color: colors.ink },
  cta: { height: 56, borderRadius: radii.sm, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, backgroundColor: colors.ink },
  ctaDisabled: { backgroundColor: colors.ter },
  ctaText: { fontSize: 16, fontWeight: "700", color: colors.onImage },
});
```

- [ ] **Step 5: Verify**

Run:
```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green; full suite still passes.

- [ ] **Step 6: Commit**

```bash
git add mobile/src/app/photo/_layout.tsx mobile/src/app/photo/select.tsx mobile/src/app/_layout.tsx "mobile/src/app/(tabs)/_layout.tsx"
git commit -m "feat(mobile): photo modal stack + 08 select screen + tab launcher"
```

---

### Task 11: 09 analyzing screen

**Files:**
- Create: `mobile/src/app/photo/analyzing.tsx`

**Interfaces:**
- Consumes: `usePhotoFlowStore` (Task 7); `Icon`, theme tokens; `expo-router` `router`.
- Produces: route `/photo/analyzing` (09). On success → `router.replace("/photo/result")`; back → abort + `router.back()`; error → inline retry/back.

- [ ] **Step 1: Build the analyzing screen**

Create `mobile/src/app/photo/analyzing.tsx`:
```tsx
import { useEffect, useRef } from "react";
import { Animated, View, Text, Pressable, Image, StyleSheet, Easing } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { usePhotoFlowStore } from "@/features/photo/stores/photo-flow-store";
import { colors, spacing, radii } from "@/constants/theme";

const MIN_VISIBLE_MS = 600;

export default function PhotoAnalyzingScreen() {
  const insets = useSafeAreaInsets();
  const asset = usePhotoFlowStore((s) => s.asset);
  const status = usePhotoFlowStore((s) => s.status);
  const startSearch = usePhotoFlowStore((s) => s.startSearch);
  const abort = usePhotoFlowStore((s) => s.abort);

  const mountedAt = useRef(Date.now());
  const anim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(anim, { toValue: 1, duration: 1300, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
    );
    loop.start();
    return () => loop.stop();
  }, [anim]);

  useEffect(() => {
    if (status !== "success") return;
    const elapsed = Date.now() - mountedAt.current;
    const wait = Math.max(0, MIN_VISIBLE_MS - elapsed);
    const t = setTimeout(() => router.replace("/photo/result"), wait);
    return () => clearTimeout(t);
  }, [status]);

  const goBack = () => {
    abort();
    router.back();
  };

  const isError = status === "error";

  const translateX = anim.interpolate({ inputRange: [0, 1], outputRange: ["-42%", "100%"] });

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.sm }]}>
      <Pressable style={styles.back} onPress={goBack} hitSlop={8}>
        <Icon name="chevron-left" size={23} />
      </Pressable>

      <View style={styles.wrap}>
        {asset ? <Image source={{ uri: asset.uri }} style={styles.thumb} /> : null}

        {isError ? (
          <>
            <Text style={styles.title}>분석하지 못했어요</Text>
            <Text style={styles.sub}>잠시 후 다시 시도해 주세요</Text>
            <View style={styles.errorActions}>
              <Pressable style={[styles.errBtn, styles.errPrimary]} onPress={() => startSearch()}>
                <Text style={styles.errPrimaryText}>다시 시도</Text>
              </Pressable>
              <Pressable style={styles.errBtn} onPress={() => router.back()}>
                <Text style={styles.errText}>돌아가기</Text>
              </Pressable>
            </View>
          </>
        ) : (
          <>
            <Text style={styles.title}>사진을 분석하고 있어요</Text>
            <Text style={styles.sub}>잠시만 기다려 주세요</Text>
            <View style={styles.bar}>
              <Animated.View style={[styles.barFill, { transform: [{ translateX }] }]} />
            </View>
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  back: { width: 40, height: 40, alignItems: "center", justifyContent: "center", marginLeft: spacing.xs },
  wrap: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 44 },
  thumb: { width: 92, height: 92, borderRadius: radii.xl, marginBottom: 26, backgroundColor: colors.inset },
  title: { fontSize: 20, fontWeight: "700", letterSpacing: -0.36, marginBottom: 6, color: colors.ink },
  sub: { fontSize: 13, color: colors.sec, marginBottom: 30 },
  bar: { width: "100%", height: 4, borderRadius: 2, backgroundColor: colors.skeleton, overflow: "hidden" },
  barFill: { width: "42%", height: "100%", borderRadius: 2, backgroundColor: colors.ink },
  errorActions: { flexDirection: "row", gap: 11, marginTop: 4 },
  errBtn: { height: 48, paddingHorizontal: 22, borderRadius: radii.sm, alignItems: "center", justifyContent: "center", backgroundColor: colors.inset },
  errPrimary: { backgroundColor: colors.ink },
  errPrimaryText: { fontSize: 15, fontWeight: "700", color: colors.onImage },
  errText: { fontSize: 15, fontWeight: "700", color: colors.ink },
});
```

> `Date.now()` is fine in app runtime code (the no-`Date.now()` rule applies only to Workflow scripts).

- [ ] **Step 2: Verify**

Run:
```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add mobile/src/app/photo/analyzing.tsx
git commit -m "feat(mobile): 09 analyzing screen (indeterminate bar, min-600ms, abort, inline error)"
```

---

### Task 12: 10 result screen

**Files:**
- Create: `mobile/src/app/photo/result.tsx`

**Interfaces:**
- Consumes: `usePhotoFlowStore` (Task 7); `sortMatches`/`SortMode` (Task 3); `ResultCard` (Task 9); `Icon`, theme tokens; `expo-router` `router`.
- Produces: route `/photo/result` (10). Card tap → `router.replace("/spots/[contentId]")`; back → `router.back()` (to 08); empty → [다른 사진으로] → back.

- [ ] **Step 1: Build the result screen**

Create `mobile/src/app/photo/result.tsx`:
```tsx
import { useMemo, useState } from "react";
import { ScrollView, View, Text, Pressable, Image, StyleSheet } from "react-native";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { usePhotoFlowStore } from "@/features/photo/stores/photo-flow-store";
import { ResultCard } from "@/features/photo/components/ResultCard";
import { sortMatches, type SortMode } from "@/features/photo/lib/sort-matches";
import { colors, spacing, radii } from "@/constants/theme";

export default function PhotoResultScreen() {
  const asset = usePhotoFlowStore((s) => s.asset);
  const result = usePhotoFlowStore((s) => s.result);
  const [mode, setMode] = useState<SortMode>("similarity");

  const matches = result?.matches ?? [];
  const hadLocation = result?.queryHadLocation ?? false;
  const sorted = useMemo(() => sortMatches(matches, mode), [matches, mode]);

  const openSpot = (contentId: string) =>
    router.replace({ pathname: "/spots/[contentId]", params: { contentId } });

  return (
    <View style={styles.root}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: spacing.xxl }}>
        <View style={styles.hero}>
          {asset ? <Image source={{ uri: asset.uri }} style={styles.heroImg} /> : null}
          <View style={styles.heroScrim} pointerEvents="none" />
          <Pressable style={styles.heroBack} onPress={() => router.back()} hitSlop={8}>
            <Icon name="chevron-left" size={22} color={colors.onImage} />
          </Pressable>
          <View style={styles.heroCopy} pointerEvents="none">
            <Text style={styles.eyebrow}>내 사진과 닮은</Text>
            <Text style={styles.heroTitle}>비슷한 장소 {matches.length}곳</Text>
          </View>
        </View>

        {matches.length === 0 ? (
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>닮은 장소를 찾지 못했어요</Text>
            <Text style={styles.emptySub}>다른 사진으로 다시 시도해 보세요</Text>
            <Pressable style={styles.emptyBtn} onPress={() => router.back()}>
              <Text style={styles.emptyBtnText}>다른 사진으로</Text>
            </Pressable>
          </View>
        ) : (
          <>
            {hadLocation ? (
              <View style={styles.sortRow}>
                <Pressable
                  style={[styles.pill, mode === "similarity" ? styles.pillOn : styles.pillOff]}
                  onPress={() => setMode("similarity")}
                >
                  <Text style={mode === "similarity" ? styles.pillTextOn : styles.pillTextOff}>유사도순</Text>
                </Pressable>
                <Pressable
                  style={[styles.pill, mode === "distance" ? styles.pillOn : styles.pillOff]}
                  onPress={() => setMode("distance")}
                >
                  <Text style={mode === "distance" ? styles.pillTextOn : styles.pillTextOff}>거리순</Text>
                </Pressable>
              </View>
            ) : null}

            <View style={styles.list}>
              {sorted.map((match) => (
                <ResultCard
                  key={match.contentId}
                  match={match}
                  showDistance={hadLocation}
                  onPress={() => openSpot(match.contentId)}
                />
              ))}
            </View>
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  hero: { height: 312, backgroundColor: colors.inset },
  heroImg: { width: "100%", height: "100%" },
  heroScrim: { position: "absolute", inset: 0, backgroundColor: colors.scrim },
  heroBack: { position: "absolute", top: 54, left: 10, width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center", backgroundColor: colors.control },
  heroCopy: { position: "absolute", left: 22, bottom: 22 },
  eyebrow: { fontSize: 11, fontWeight: "700", letterSpacing: 2, textTransform: "uppercase", color: colors.onDim },
  heroTitle: { fontSize: 27, fontWeight: "800", letterSpacing: -0.5, marginTop: 5, color: colors.onImage },
  sortRow: { flexDirection: "row", gap: 7, paddingHorizontal: spacing.lg, paddingTop: 18, paddingBottom: 8 },
  pill: { paddingHorizontal: 15, paddingVertical: 8, borderRadius: radii.pill },
  pillOn: { backgroundColor: colors.ink },
  pillOff: { backgroundColor: colors.fill },
  pillTextOn: { fontSize: 13, fontWeight: "700", color: colors.onImage },
  pillTextOff: { fontSize: 13, fontWeight: "700", color: colors.sec },
  list: { gap: 14, paddingHorizontal: spacing.lg, paddingTop: 8 },
  empty: { alignItems: "center", paddingHorizontal: spacing.xl, paddingTop: 48, gap: 8 },
  emptyTitle: { fontSize: 18, fontWeight: "700", color: colors.ink },
  emptySub: { fontSize: 14, color: colors.sec, marginBottom: 12 },
  emptyBtn: { height: 52, paddingHorizontal: 24, borderRadius: radii.sm, alignItems: "center", justifyContent: "center", backgroundColor: colors.ink },
  emptyBtnText: { fontSize: 15, fontWeight: "700", color: colors.onImage },
});
```

- [ ] **Step 2: Verify**

Run:
```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.

- [ ] **Step 3: Manual smoke (device/simulator) — flow + KTO**

Confirm: Photo tab → 08 (empty, CTA disabled) → pick gallery (no permission prompt) → CTA enabled → 분석하기 → 09 (bar animates ≥600ms) → 10 (hero = my photo, "비슷한 장소 N곳"). If location already granted, sort chips appear and toggle re-sorts; otherwise no chips and no distance text. Tap a card → spot detail (07). Back from 09 mid-flight aborts → 08 with photo retained. 0-match response → 10 empty state. **Verify the expo-router replace into `/spots/[contentId]` from the modal group lands correctly and back behaves as intended (design §1 verification item).**

- [ ] **Step 4: Commit**

```bash
git add mobile/src/app/photo/result.tsx
git commit -m "feat(mobile): 10 result screen (hero, sort chips, empty state, replace→spot)"
```

---

## Self-Review

**1. Spec coverage:**
- Navigation (modal stack, tab intercept, 09→10 replace, 10→07 replace, abort) → Tasks 10–12. ✓
- 08 states (empty/selected, camera/gallery, permission-denied, CTA gating, location attach) → Tasks 5, 10. ✓
- 09 (indeterminate bar, min-600ms, abort, retry, err.code unified copy) → Task 11 (errorCode from store Task 7; copy is code-agnostic). ✓
- 10 (local hero, N곳, sort chips GPS-only, client sort, empty state, bucket labels, conditional distance) → Tasks 3, 8, 9, 12. ✓
- KTO (memory-only upload, reset on flow exit, local hero) → Tasks 6 (FormData), 7 (reset), 10 (reset cleanup), 12 (local asset hero). ✓
- Similarity bucket labels, formatDistance reuse → Tasks 2, 8, 9. ✓
- expo-image-picker only + config plugin → Task 1. ✓
- Tests for each testable unit → Tasks 2–9. ✓

**2. Placeholder scan:** No TBD/TODO; every code step has complete code. The 10→07 expo-router resolution is flagged as a real runtime verification item (Task 12 Step 3), not a placeholder.

**3. Type consistency:** `PhotoMatch`/`PhotoSearchResult` (Task 1) used identically in Tasks 3, 6, 7, 9, 12. `PickedImage`/`PickResult` (Task 5) used in Tasks 6, 7, 10. `Coords` (Task 4) used in Tasks 6, 7. `bucketFor` (Task 2) used in Task 8. `sortMatches`/`SortMode` (Task 3) used in Task 12. Store action names (`setAsset`/`clearAsset`/`startSearch`/`abort`/`reset`) consistent across Tasks 7, 10, 11, 12.

## Known deviations (recorded)
- **10 → 07 = `replace`** per task brief + P0/P1 design doc, vs S04 §10 `push`. Trade-off (loses result list on back) recorded in the design spec §1.
- **Request fired at 08** via `startSearch()` (store owns lifecycle); 09 reads status. Equivalent to S04's "fire at 08, 09 waits".
