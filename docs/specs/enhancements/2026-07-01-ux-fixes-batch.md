# UX Fixes Batch — 2026-07-01

Seven targeted fixes across mobile, backend, and admin. Branch `feat/ux-fixes-batch`.

## 1. Map bottom sheet — minimum height keeps one list item visible
`mobile/src/features/map/components/MapBottomSheet.tsx`. The lowest snap (`peek`,
`H * 0.88`) hides the list. Change `peek` so the collapsed panel still reveals the
drag handle + category chips + exactly one `NearbyCard` above the tab bar. Compute
`peek` from a fixed visible-height budget instead of a screen ratio.

## 2. Map query bbox excludes the panel-covered area
`mobile/src/features/map/stores/map-store.ts` (+ `map.tsx`, `lib/`). Markers and
"이 지역에서 검색" must query only the map region **visible above the panel**. Clip
the south latitude of the query bbox by the fraction of the screen the panel covers
at the current snap: `visibleSouthLat = ne.lat - (ne.lat - sw.lat) * (panelTopY / H)`
where `panelTopY = SHEET_SNAP_Y[snap]`. Apply to both auto-viewport queries and
`searchHere`.

## 3. Region picker column widths
`mobile/src/features/map/components/RegionPicker.tsx` line ~136: left 시/도 column is
`width: 96` (too wide). Make left narrower (~72) so the right 시군구 column (flex:1)
gets more room.

## 4. Admin console responsive on mobile
`admin.css` + `curation.css`, edited **identically** in both
`admin/mockups/assets/` and `backend/app/modules/admin/static/assets/` (byte-identical
per CI drift check `.github/scripts/check-admin-mockup-drift.sh`). Add narrow-viewport
media queries: collapse the fixed `250px` sidebar into a top/hamburger nav or stacked
column, reduce padding, single-column the 3-column curation `.editor`
(`236px minmax(372px,1fr) 348px`), horizontal-scroll tables.

## 5. Random nickname on account creation
`backend/app/modules/users/`. New users currently store the OAuth `name` claim or NULL.
Assign a generated random Korean nickname on creation (OAuth + email) regardless of the
provider name. New util (e.g. `app/core/nickname.py`, adjective+noun+number). No schema
change (`users.name` VARCHAR(50) already exists, nullable). Add tests.

## 6. Detail overview strips HTML tags
`mobile/src/features/spots/components/IntroSection.tsx` renders KTO `overview` verbatim,
so `<br>` etc. appear as literal text. Add a **render-time** HTML→plaintext util
(`mobile/src/lib/html-text.ts`): decode entities, convert `<br>`/`</p>`/`</div>` to
newlines, strip remaining tags, collapse whitespace. Stored data untouched (storage stays
verbatim per CLAUDE.md; this is display-only).

## 7. "전체 사진" viewer shows full image
`mobile/src/features/spots/components/PhotoViewer.tsx` +
`mobile/src/components/RemoteImage.tsx`. `resizeMode` is passed as a style (ignored) and
`RemoteImage` hardcodes `cover`, cropping the photo. Add a `resizeMode` prop to
`RemoteImage`; in `PhotoViewer` fill full width/height with `resizeMode="contain"`
(drop the `height * 0.8`).
