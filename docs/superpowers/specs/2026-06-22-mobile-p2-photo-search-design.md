# PicTrip Mobile — P2 Photo Search / CLIP (Design)

Date: 2026-06-22 · Branch: `feat/mobile-p2-photo-search` (off `main` after PR #3 merge)

## Context

P2 implements the **photo-search flow** (08 사진 선택 → 09 분석중 → 10 결과 → 07 스팟
상세) on top of the merged P0 foundation + P1 guest discovery. The flow is a
**modal stack** launched by intercepting the Photo tab press; the tab itself
never renders a screen.

UX, navigation, compliance, and empty/error states are already locked by the
screen spec `docs/specs/screens/S04-photo-search.md` (C1–C3, per-screen detail)
and the contest constraints in `docs/specs/_context/session-context.md`. This
document is the **mobile implementation mapping** — how S04 lands in the
codebase: route wiring, feature module shape, ephemeral flow state, location
handling, components, error branching, and tests. It reuses every P0/P1 pattern
(api-client JSend single-unwrap, `AppError`/`err.code` branching, monochrome
theme tokens, line-SVG `Icon`, `RemoteImage`, `formatDistance`).

### Backend contract (verified against `backend/app/modules/taste/`)

```
POST /taste/photo-search
  multipart/form-data: image (required)
  query: lat, lng (both optional; distance computed only when both present)
→ JSend data: {
    matches: [ SpotCard + {
      similarity,        // float 0..1 (1 - cosine distance, clamped)
      distance?,         // metres from query point; present only when lat/lng sent
      regionName?, sigunguName?
    } ],
    queryHadLocation: boolean
  }
```

- 200 with empty `matches` is a **valid success** (designed empty state), not an
  error. Real errors (400 `IMAGE_INVALID`, 5xx, network, timeout) surface on 09.
- The server applies a calibrated similarity floor with a top-N soft floor and
  sorts by similarity desc. The client never re-requests for sorting.

### Locked decisions feeding this spec

- **New dependency:** `expo-image-picker` only (Expo-vetted first-party; same
  precedent as `react-native-svg`). It covers **both** camera capture
  (`launchCameraAsync`) and gallery (`launchImageLibraryAsync`) — no
  `expo-camera`. `expo-location` already present (P0).
- **Similarity display = bucket labels** ("매우 닮음 / 닮음 / 비슷함"), never raw
  `round(cosine×100)%` (S11 §2: raw cosine reads deceptively low). The gauge
  ring visual is kept, filled to the bucket tier; no number rendered.
- **10 → 07 navigation = `replace`** (this task's brief + P0/P1 design doc
  line 72). **Deviation noted:** S04 §10 specifies `push` (back from 07 returns
  to the result list for continued browsing). `replace` is honored as the
  controlling instruction; trade-off recorded in §1.
- **Request fired at 08** ("분석하기") via a store action that owns the request
  lifecycle, so it survives the 08→09 navigation and 09 owns abort/retry. S04
  §09 wording ("요청은 08에서 발사, 09는 대기") is satisfied exactly.
- **Ephemeral zustand flow store, not TanStack Query.** Photo results are
  non-cacheable (KTO: image bytes + result are memory-only, released on flow
  exit) and the flow is imperative/transient — caching is wrong here.

## Navigation architecture

```
src/app/
├── _layout.tsx                 (P0) root Stack — register `photo` group
├── (tabs)/_layout.tsx          (P1) intercept Photo tabPress → push /photo/select
├── (tabs)/photo.tsx            (P1 stub) unreachable via tab press; kept for Tabs.Screen
└── photo/
    ├── _layout.tsx          ★ Stack, presentation: "modal", headerShown: false
    ├── select.tsx           ★ 08 사진 선택
    ├── analyzing.tsx        ★ 09 분석중
    └── result.tsx           ★ 10 결과
```

### 1. Navigation rules (S04 C1, with the replace deviation)

- **Entry:** Photo tab `Tabs.Screen` gets
  `listeners={{ tabPress: (e) => { e.preventDefault(); router.push('/photo/select'); } }}`.
  The tab screen never renders (stub retained so the typed-route tree compiles).
- **08 → 09:** `router.push('/photo/analyzing')` (request already fired at 08).
- **09 → 10:** `router.replace('/photo/result')` on success → back from 10 skips
  09 and lands on 08.
- **09 back:** abort in-flight request, `router.back()` to 08 (selected image
  retained).
- **10 → 07:** `router.replace({ pathname: '/spots/[contentId]', params: { contentId } })`.
  - *Trade-off:* with `replace`, back from 07 → 08 and the result list is gone
    (cannot pick another match). `push` (S04) would preserve the list. We follow
    the brief (`replace`); revisit if continued-browsing UX is desired.
  - *Verification item:* confirm expo-router resolves `/spots/[contentId]` from
    inside the modal group and that back behavior matches at runtime.
- **Flow exit** (any back to 08 then back, or completing into 07): call
  `photoFlowStore.reset()` to release the image reference (KTO).

## Feature module — `src/features/photo/`

Mirrors the P1 module layout (`api.ts` · `stores/` · `usecases/` ·
`components/` · `lib/`). File naming: components PascalCase, runtime modules
kebab-case.

| Unit | File | Responsibility |
|---|---|---|
| API | `api.ts` | `photoSearch(asset, coords, signal)` → builds `FormData` (`image` part from local URI + mime + name), `api.post('/taste/photo-search', form, { params: coords, signal })`. api-client already unwraps JSend → returns `PhotoSearchResult`. **No re-unwrap.** |
| Flow store | `stores/photo-flow-store.ts` | zustand. State: `asset: PickedImage \| null`, `coords: Coords \| null`, `status: 'idle'\|'loading'\|'success'\|'error'`, `result: PhotoSearchResult \| null`, `errorCode: ErrorCode \| null`, `controller: AbortController \| null`. Actions: `setAsset`, `clearAsset`, `startSearch()` (reads coords via usecase, fires `photoSearch` with a fresh AbortController, sets status/result/errorCode), `abort()`, `reset()` (release asset + result, clear all). |
| Pick image | `usecases/pick-image.ts` | `pickFromLibrary()` → `launchImageLibraryAsync({ mediaTypes: ['images'], allowsMultipleSelection: false, quality })`; **no permission popup** (system picker). `captureFromCamera()` → just-in-time `requestCameraPermissionsAsync()`; granted → `launchCameraAsync`; denied → return a `permission-denied` sentinel so 08 can offer `Linking.openSettings()`. Cancel → `null`. Returns `PickedImage { uri, mimeType, fileName }`. |
| Location | `usecases/get-last-known-coords.ts` | `getForegroundPermissionsAsync()` (**never** request). If `granted` → `getLastKnownPositionAsync()` → `{ lat, lng }`; else `null`. Fast, no fresh-fix wait, never triggers a permission prompt (S04 위치 결정). |
| Similarity bucket | `lib/similarity-bucket.ts` | `bucketFor(similarity) → { label: '매우 닮음'\|'닮음'\|'비슷함', tier: 0..1 }`. Thresholds are documented tunable constants (initial: ≥0.75 / ≥0.65 / else). |
| Sort | `lib/sort-matches.ts` | `sortMatches(matches, mode)`: `'similarity'` = similarity desc; `'distance'` = distance asc, similarity desc tiebreak (nulls last). |

### Why a store action instead of `useMutation`

The request must be (a) fired on 08, (b) observed on 09 for loading/abort/retry,
(c) its result read on 10 — three separate screens. A component-scoped
`useMutation` cannot span them, and the local image URI must travel with it.
A zustand action that holds the `AbortController` and result is the minimal
construct that satisfies all three while keeping everything in memory (KTO).

## Screen behavior (S04 §08–§10)

### 08 — `select.tsx`
- States: **empty** (dashed placeholder + "사진을 고르세요", CTA disabled gray) /
  **selected** (preview cover + top-right X remove, CTA active ink).
- 촬영 / 갤러리 = two secondary (inset) buttons. 분석하기 = ink CTA with `sparkle`
  icon; enabled only when `asset != null`.
- 분석하기 handler: `await getLastKnownCoords()` (silent) → `setAsset` already
  set → `startSearch()` → `router.push('/photo/analyzing')`.
- Camera-permission-denied → inline "설정에서 카메라 권한을 켜 주세요" + settings
  deep link. Gallery cancel = no-op (state unchanged). Re-pick replaces the
  single slot.

### 09 — `analyzing.tsx`
- 92px thumbnail (`asset.uri`) + "사진을 분석하고 있어요" + "잠시만 기다려 주세요" +
  **indeterminate bar** (RN `Animated.loop`, no SVG needed). **Min ~600ms**
  display gate (track mount time; defer the 10 replace if response is faster).
- Subscribes to store `status`. `success` → after the gate, `router.replace('/photo/result')`.
  Note: 0 matches is `success` → routes to 10 empty, **not** error.
- Back (`←`) → `store.abort()` → `router.back()` to 08 (asset retained).
- `error` → inline block replaces the bar: "분석하지 못했어요" / "잠시 후 다시 시도해
  주세요" + **[다시 시도]** (`startSearch()` again, back to loading) / **[돌아가기]**
  (to 08). Copy is unified across all `errorCode`s; branch on `err.code` only.

### 10 — `result.tsx`
- Hero (312px) = **local `asset.uri`** (never a server image) + scrim. Eyebrow
  "내 사진과 닮은" + title "비슷한 장소 N곳" (N = matches length). Back `←` → 08.
- Sort chips (유사도순 default / 거리순) rendered **only when `queryHadLocation`**.
  Tap re-sorts client-side via `sortMatches`; no refetch.
- Card list = `ResultCard` per match.
- **empty (0 matches):** hero retained, body "닮은 장소를 찾지 못했어요" / "다른
  사진으로 다시 시도해 보세요" + [다른 사진으로] → 08. No sort chips.

## Components & tokens

- `components/ResultCard.tsx` — `RemoteImage` (KTO URL) + glass bar (`colors.scrim`
  / `glassFill` / `glassBorder`): name (1 line) / meta "category · {regionName}
  {sigunguName} [· distance]" + `SimilarityGauge`. Distance shown only when
  `queryHadLocation && distance != null`, via `formatDistance`. Tap → `replace`
  to spot detail.
- `components/SimilarityGauge.tsx` — circular ring (react-native-svg) filled to
  `bucket.tier`, no number; bucket `label` shown as adjacent text. Monochrome.
- `Icon.tsx` — add two line-SVG glyphs: `image` (gallery), `sparkle` (analyze
  CTA). `camera` / `close` / `sort` / `chevron-left` already exist.
- `lib/api-types.ts` — add `PhotoMatch` (`SpotCard & { similarity: number;
  distance?: number \| null; regionName?: string \| null; sigunguName?: string \|
  null }`) and `PhotoSearchResult { matches: PhotoMatch[]; queryHadLocation:
  boolean }`.

## Error handling & KTO compliance

- All failures are caught on 09 and branched on `err.code` (never `err.message`),
  collapsed to one user copy. `IMAGE_INVALID` / `VALIDATION_FAILED` /
  `KTO_API_UNAVAILABLE` / `NETWORK_ERROR` / 5xx all → "분석하지 못했어요". 10 is
  only ever entered with success data.
- **KTO invariants:** image bytes go into `FormData` for the single upload and
  are never persisted/logged client-side; the `asset` URI lives only in store
  memory and is released on `reset()`. The result hero uses the local asset, not
  a server-returned user-image URL (the contract returns none).

## Testing (jest-expo, mirrors P0/P1 unit-first approach)

- `similarity-bucket` — threshold → label + tier mapping (boundaries).
- `sort-matches` — distance asc with similarity tiebreak; nulls last.
- `photo-flow-store` — `startSearch` transitions idle→loading→success/error;
  `abort()` cancels and resets controller; `reset()` releases asset + result.
- `pick-image` — camera path calls `requestCameraPermissionsAsync`; library path
  does **not**; cancel → null (expo-image-picker mocked).
- `get-last-known-coords` — when permission not granted, returns null **without**
  calling any request API; granted → coords (expo-location mocked).
- `ResultCard` / `SimilarityGauge` render — bucket label shown; distance present
  only when provided.
- `api.ts photoSearch` — builds FormData with the `image` part and passes
  lat/lng params + signal (axios mocked).

## New dependency

`expo-image-picker` via `expo install`. Config-plugin usage strings in app
config: iOS `NSPhotoLibraryUsageDescription`, `NSCameraUsageDescription`
(Korean copy). No other native modules.

## Out of scope (later phases)

P3 OAuth login + save/profile (10 cards have no inline save — save lives on 07),
P4 map + permissions + region picker, P5 legal + deep links. Saving a matched
spot remains the inert 07 button until P3.

## Verification (before declaring done)

`cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test`
— all green; new tests pass alongside the existing 27.
