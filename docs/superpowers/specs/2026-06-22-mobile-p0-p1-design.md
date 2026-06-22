# PicTrip Mobile — P0 Foundation + P1 Discovery (Design)

**Date:** 2026-06-22
**Scope:** Build phases P0 (foundation infra) and P1 (guest discovery flow) of the
Expo mobile app. Later phases (P2 photo-search, P3 auth+save, P4 map, P5 finish)
get their own spec → plan → implementation cycles.
**Status:** Approved for implementation.

## Context

`mobile/` is a near-blank Expo Router scaffold (SDK 56 · RN 0.85 · React 19.2 ·
TS strict). Only `src/constants/theme.ts` and `src/lib/api-types.ts` stubs exist;
`src/app/` is empty. The backend API contract (Stage-A, merged in PR #2) is the
SSOT — `backend/app/modules/*/routes.py` + `schemas.py`. Design SSOT is
`docs/mockups/` (16 monochrome screens). Product/UX SSOT is `docs/specs/`
(S01→S12) and `docs/specs/_context/session-context.md`.

This machine cannot reach the prod DB (CT110) or the live API (Cloudflare WAF
blocks automated curl with 1010). Real devices / Expo client reach it fine.
Implementation is driven from the backend source contract, not live calls.

### Locked decisions feeding this spec

- **Onboarding routing = local flag only.** Splash branches on an AsyncStorage-style
  `onboarding_seen` flag (stored in expo-secure-store to avoid a new native dep).
  The server's `isOnboarded` is hardcoded `false` everywhere
  (`users/services.py:77`, `core/auth.py:129,159`) and is **never** read for
  routing — doing so would trap users in onboarding forever. Onboarding = a
  3-slide intro carousel only (no mood/taste selection; there is no
  `POST /taste/moods` endpoint and `MAX_5_MOODS` is unused by mobile).
- **Build order = P0→P5 sequential.** This spec covers P0 + P1.
- **Icons = `react-native-svg`** (`expo install`), treated as the Expo-vetted
  exception to "no new native modules" — the only realistic way to port the
  mockups' Lineicons as line-SVG `<Icon>`.
- **JSend everywhere.** Every response is `{ data, error, meta }`. Mobile branches
  on `err.code`, never `err.message`.
- **Auth model (relevant to P0 boot only).** access=memory, refresh=secure-store
  (`WHEN_UNLOCKED_THIS_DEVICE_ONLY`); denylist fail-open; sliding refresh remint.
  Full OAuth login lands in P3; P0 only does the boot silent-refresh attempt.

## Navigation architecture (Expo Router)

Full route tree. **Bold** = implemented this session; others are placeholder
stubs that render a "coming soon" state so the shell compiles and the tab bar is
navigable.

```
src/app/
├── _layout.tsx              ★ Root: QueryClient + SafeArea providers, root Stack
├── index.tsx                ★ Splash / boot gate: hydrate onboarding_seen +
│                              attempt silent refresh → redirect to onboarding or tabs
├── onboarding.tsx           ★ 02 intro carousel (full screen, no tab bar)
├── (tabs)/
│   ├── _layout.tsx          ★ 4-tab bottom bar (Home · Map · Photo · My)
│   ├── index.tsx            ★ 05 Home feed
│   ├── map.tsx              · 11 Map (P4 stub)
│   ├── photo.tsx            · Photo launcher (P2 stub; tab press launches photo stack)
│   └── profile.tsx          · 14/15 My (P3 stub)
├── curations/[slug].tsx     ★ 06 Curation detail (push)
├── spots/[contentId].tsx    ★ 07 Spot detail (push; save button is no-op until P3)
├── photo/{select,analyzing,result}.tsx   · P2
├── (modals)/{login,permissions,region-picker}.tsx  · P3 / P4
├── saved.tsx                · 13 Saved grid (P3)
└── legal/[doc].tsx          · 16 Legal (P5)
```

**Navigation rules** (S1 §5.1):
- Curation detail (06) and Spot detail (07) push within the current tab.
- Photo flow, login, permissions, region picker = modal stacks over the current tab.
- The Photo tab button does **not** render a tab screen — it intercepts the tab
  press and launches the photo modal stack (P2). For P0 the tab is a stub.
- Results (10) → Spot detail (07) uses `replace` (P2).

### Splash boot gate logic (`index.tsx`)

```
hydrate:
  - read onboarding_seen flag (secure-store)
  - read refresh token (secure-store); if present, attempt POST /auth/refresh
    - success → set access token in memory + user in auth-store
    - failure → quiet guest demotion (clear tokens, no toast, no retry)
branch:
  - no onboarding_seen          → redirect /onboarding
  - has onboarding_seen         → redirect /(tabs)   (login status irrelevant)
```

The flag is written only on explicit onboarding exit ("사진으로 시작하기" or
"건너뛰기"), set **before** navigating away to prevent re-entry. Mid-carousel app
kill leaves no flag → re-entry next boot.

## P0 — Foundation units

No screens; pure infrastructure. Each unit has one clear responsibility.

| Unit | File | Responsibility |
|---|---|---|
| Design tokens | `src/constants/theme.ts` | Port all mockup CSS variables — colors (`ink #171719`, `sec #5A5C63`, `ter #9396A0`, `line`, `fill`, `inset #F7F7F8`, `skeleton #ECEDEF`, `bg #FFFFFF`), scrim/glass overlays, type scale, spacing, radii, shadows. Monochrome only — no rose/color. |
| Icon | `src/components/Icon.tsx` | react-native-svg line-icon registry. Initial set: chevron-left, chevron-right, share, heart, heart-fill, home, map-pin, camera, person, location, close, search, recenter, sort. Props: `name`, `size`, `color`, `strokeWidth`. |
| API client | `src/lib/api-client.ts` | axios instance; `baseURL = EXPO_PUBLIC_API_BASE`. **Response interceptor unwraps JSend**: on success returns `response.data.data`; on error throws `AppError` built from `response.data.error`. Request interceptor injects `Authorization: Bearer <accessToken>` from auth-store. **On 401 → refresh once → retry** original request; refresh failure → guest demotion + rethrow. |
| App error | `src/lib/app-error.ts` | `AppError { code, message, status, details }`. Code union mirrors `backend/app/core/exceptions.py` (`VALIDATION_FAILED`, `AUTH_TOKEN_INVALID`, `AUTH_TOKEN_EXPIRED`, `GUEST_FORBIDDEN`, `PERMISSION_DENIED`, `RESOURCE_NOT_FOUND`, `DUPLICATE_RESOURCE`, `MAX_5_MOODS`, `IMAGE_INVALID`, `RATE_LIMITED`, `KTO_API_UNAVAILABLE`, `LBS_CONSENT_REQUIRED`, `OAUTH_PROVIDER_UNAVAILABLE`, `OAUTH_ID_TOKEN_INVALID`, `LLM_API_UNAVAILABLE`, `AUTH_SESSION_REVOKED`, `SESSION_STORE_UNAVAILABLE`, `INTERNAL_ERROR`). |
| Query client | `src/lib/query-client.ts` | TanStack QueryClient. `retry`: do **not** retry on 4xx `AppError`; retry network/5xx up to 2×. Sensible `staleTime` defaults. |
| Distance util | `src/lib/distance.ts` | `formatDistance(m)`: `<1000 → "{int}m"`; `1000–9999 → "{1-dp} km"`; `≥10000 → "{int} km"`. Shared by photo-search (P2) and map (P4). |
| Storage | `src/lib/storage.ts` | Thin wrappers over expo-secure-store: `getRefreshToken/setRefreshToken/clearRefreshToken` (`WHEN_UNLOCKED_THIS_DEVICE_ONLY`) and `getOnboardingSeen/setOnboardingSeen`. **No AsyncStorage dependency added.** |
| Auth store | `src/features/auth/stores/auth-store.ts` | zustand. State: `accessToken` (memory only), `user`, `isAuthenticated`. Actions: `setSession(tokenPair)`, `clear()`, `hydrateFromRefresh()`. P0 uses only boot silent-refresh; OAuth login actions land in P3. |
| API types | `src/lib/api-types.ts` (extend stub) | JSend envelope + canonical `SpotCard` already stubbed; extend with `HomeFeed`, `Curation`, `SpotDetail`, `NearbySpot`, `TokenPair`, `User`, congestion union. Match backend camelCase field names exactly. |

### Shared components (P0, used across P1+)

- `AppBar` — circular nav buttons (back / share / action), centered title.
- `SpotCard` — canonical card: `RemoteImage` + title + category label + optional
  `CongestionChip`. Tap → spot detail.
- `CongestionChip` — `low | medium | high`; hidden when `null`.
- `PrimaryButton` — full-width ink button (54–56px), `secondary` variant on inset.
- `RemoteImage` — KTO image URL with skeleton placeholder + graceful fallback
  when `firstImageUrl` is null. URLs used as-is (already HTTPS-upgraded server-side).
- `Skeleton` — shimmer placeholder block.
- `Rail` — horizontal snap carousel wrapper.

## P1 — Discovery (guest, no auth)

Feature modules under `src/features/<domain>/` (`api/` · `queries/` ·
`components/` · `types`):

- **`features/feed/`** — `getHomeFeed()` → `GET /home/feed`; `useHomeFeed()`.
  - `HeroCarousel`: 6 region heroes, manual swipe + snap + 6-dot indicator (no
    auto-scroll). Title preserves `\n` (render as multi-line). Tap → curation detail.
  - `MoodRail`: 3 mood rails, ≤8 cards each, rendered via shared `Rail` + `SpotCard`.
    Tap card → spot detail.
- **`features/curation/`** — `getCuration(slug)` → `GET /curations/{slug}`;
  `useCuration()`. Renders `title` + `lead` + `intro` + 2-column grid of ≤8 `SpotCard`s.
- **`features/spots/`** — `getSpot(contentId)` → `GET /spots/{contentId}`;
  `useSpot()`; `getNearby(lat,lng)` → `GET /map/nearby` (public, no auth needed).
  Components: `Gallery` (horizontal strip → full-screen pager, no zoom),
  `IntroSection` (overview 4-line clamp + expand toggle, KTO text **verbatim**),
  `LocationSection` (address/hours/phone/homepage rows; map preview deferred to P4),
  `NearbyRail` (nearby spots with fine-category label + distance + congestion chip).

### Implemented screens this session

1. **Splash gate** (`index.tsx`) — boot logic above.
2. **Onboarding** (`onboarding.tsx`) — 3-slide intro carousel, scroll-snap, dots,
   CTA "사진으로 시작하기" + "건너뛰기". Sets `onboarding_seen` before navigating.
3. **Home feed** (`(tabs)/index.tsx`) — sticky wordmark bar, hero carousel, 3 mood
   rails. Loading = skeletons; error = retry state.
4. **Curation detail** (`curations/[slug].tsx`) — cover, title/lead/intro, 2-col grid.
5. **Spot detail** (`spots/[contentId].tsx`) — hero+scrim, title/subline, intro,
   gallery, location info, nearby rail. **Save button rendered but inert** (no-op)
   until P3 wires auth + `POST /users/me/saved/{id}`.

Tab stubs (`map`, `photo`, `profile`) render a minimal "coming soon" placeholder so
the shell is complete and navigable.

## Error handling

- `api-client` normalizes every failure to `AppError { code, message, status, details }`.
- Global 401 `AUTH_TOKEN_EXPIRED` → refresh once → retry; refresh failure → quiet
  guest demotion (clear tokens). `AUTH_SESSION_REVOKED` → clear + (P3) route to login.
- Network / 5xx → query error state with a retry affordance.
- UI copy is keyed by `err.code` (Korean strings owned by mobile); the server
  `message` is only a fallback display string, never a branch condition.
- Null fields degrade honestly: null image → fallback tile; null congestion → no
  chip; null intro fields → row hidden.

## Testing

jest-expo. Favor pure-logic units (no RN renderer dependency, so no new test libs):

- `api-client`: JSend unwrap on success; `AppError` mapping on error envelope;
  401→refresh→retry happy path and refresh-failure demotion (axios mocked).
- `distance.formatDistance`: boundary cases (999m, 1000m, 9999m, 10000m).
- congestion bucketing helper.
- `auth-store`: `setSession` / `clear` / hydrate transitions.
- `storage`: secure-store wrappers (mocked).
- 1–2 component smoke renders (`SpotCard`, `CongestionChip`) if jest-expo's
  react-test-renderer suffices without extra deps.

## Verification (before declaring done)

From `mobile/`: `npm run lint && npm run typecheck && npm run format:check && npm test`.
Missing config files (eslint/prettier/jest/babel) will be added in P0 as part of
foundation so these commands pass.

## Out of scope (later phases)

- P2: photo-search flow (08→09→10), multipart upload, results sorting.
- P3: OAuth login sheet, token lifecycle wiring, save/scrap, profile, logout/delete.
- P4: map (KakaoWebMap WebView), nearby bottom sheet, permissions, region picker,
  spot-detail map preview.
- P5: legal WebViews, deep-link handlers, final polish.

## New dependencies

- `react-native-svg` (via `expo install`) — icons. The only new native module;
  Expo-vetted. No AsyncStorage (flag reuses secure-store). No other native modules.
