# Final fix wave — PicTrip backend port (branch `port/backend`)

## FIX 1 — OAuth audience-validation bypass (CRITICAL)
**File:** `app/core/oidc.py`
- Added an early guard in `_verify_generic`: when `audiences` is empty/falsy it now
  raises `OAuthProviderUnavailable()` (provider misconfigured/disabled) BEFORE
  calling `jwt.decode`. Previously `jwt.decode(..., audience=audiences or None)`
  passed `None`, which makes PyJWT skip `aud` validation entirely — so with the
  default `GOOGLE_CLIENT_IDS=[]` / `APPLE_BUNDLE_ID=None` ANY validly-signed
  google/apple id_token was accepted (token-substitution / account takeover).
- Changed the decode call to `audience=audiences` (now guaranteed non-empty).
- Kakao path is untouched (kakao verification lives in `kakao_oidc`).
- Decision: used the in-`oidc` raise (the prompt said it "is sufficient" and is
  the cleaner option) rather than a `Settings` `model_validator`, so a
  kakao-only production deployment is not forced to configure google/apple.

**Tests added (`tests/test_oauth_providers.py`):**
- `test_google_happy_path` (pre-existing) covers case (a): an `aud` matching a
  configured `GOOGLE_CLIENT_IDS` still verifies.
- `test_google_rejected_when_no_audience_configured` — case (b). Sets
  `GOOGLE_CLIENT_IDS=[]`, mints an otherwise-valid token, asserts:
  `with pytest.raises(OAuthProviderUnavailable): await verify_oauth_id_token("google", token, ...)`
  — proving the empty-audience token is REJECTED, not silently accepted.
- `test_apple_rejected_when_no_bundle_id_configured` — mirror for apple with
  `APPLE_BUNDLE_ID=None`, same `pytest.raises(OAuthProviderUnavailable)` assertion.

## FIX 2 — Remove unauthenticated WIP placeholder route
**File:** `app/modules/images/routes.py`
- Removed `GET /admin/embeddings/status` (returned hardcoded
  `{"placeholder":"IMG-001"}`, no auth). IMG router is now empty (no operations);
  it stays defined and is still mounted by `app/main.py` (empty `APIRouter`
  mounts cleanly; `main.py` imports unchanged, suite green).
- No test covered the placeholder (grep for `embeddings/status|IMG-001|
  embeddings_status|placeholder` returned nothing in `tests/`).
- Side effect: `tests/test_health.py::test_openapi_schema_includes_all_6_domains`
  collected tags from operations only, so the IMG tag no longer appears — updated
  that test's expected set (dropped IMG tag; with a clarifying comment).

## FIX 3 — Remove dead IMG neighbor functions
**File:** `app/modules/images/services.py`
- Pre-fix verification grep over `app/`:
  ```
  app/modules/images/services.py:9:async def find_neighbor_content_ids(
  app/modules/images/services.py:61:async def find_neighbors_by_vector(
  app/modules/images/services.py:71:    Mirrors `find_neighbor_content_ids` but binds the query vector directly
  app/modules/images/services.py:95:async def find_neighbor_ids_by_vector_direct(
  app/modules/taste/services.py:25:from app.modules.images.services import find_neighbor_ids_by_vector_direct
  app/modules/taste/services.py:79:    pairs = await find_neighbor_ids_by_vector_direct(session, embedding, limit=cap)
  ```
  → `find_neighbor_content_ids` / `find_neighbors_by_vector` had NO caller
  outside their own definitions; only `find_neighbor_ids_by_vector_direct` is
  live (used by taste photo-search).
- Deleted both dead functions. KEPT `find_neighbor_ids_by_vector_direct`.
- Deleted their dedicated test files (each tested ONLY the dead fn):
  `tests/test_images_services_neighbors.py`,
  `tests/test_images_services_neighbors_by_vector.py`.
- Post-fix grep confirms only the live fn + its taste caller remain:
  ```
  app/modules/images/services.py:9:async def find_neighbor_ids_by_vector_direct(
  app/modules/taste/services.py:25:from app.modules.images.services import find_neighbor_ids_by_vector_direct
  app/modules/taste/services.py:79:    pairs = await find_neighbor_ids_by_vector_direct(session, embedding, limit=cap)
  ```

## FIX 4 — Saved-list card category source
**Files:** `app/modules/spots/services/saved.py`, `app/modules/users/routes.py`
- `list_saved_spots` now `LEFT JOIN lcls_systm_codes ON lcls_systm3_cd = spots.lcls_systm3`
  (same join feed/curation/nearby use) and populates `SpotCardRow.lcls_systm3_nm`.
- `users/routes.py` saved-list serialization now reads `category=r.lcls_systm3_nm`
  (canonical subtype label) instead of `r.category` (always None). `congestion`
  behavior unchanged.
- Test added `tests/test_users_me_saved.py::test_saved_card_category_is_subtype_label`
  — seeds a `lcls_systm_codes` row ("사적지") + a spot referencing it, saves it,
  asserts `card["category"] == "사적지"`.

## FIX 5 — Stale "crowd" OpenAPI tag + map docstrings
**Files:** `app/modules/map/routes.py`, `app/modules/map/__init__.py`, `app/modules/map/models.py`
- Router tag `"MAP · map/crowd"` → `"MAP · map"`.
- `__init__.py` module docstring "map/crowd domain" → "map domain (nearby + region)".
- `models.py` docstring corrected (nearby is sourced from SPT `spots` + congestion
  buckets, not "live crowd data in Redis").
- `services.py` comment already documented crowd-merge as removed — left as-is.

## FIX 6 — Hoist `_cover_url`
**Files:** `app/modules/spots/services/cards.py` (+ `feed.py`, `curations.py`)
- Added `cover_url(session, cover_spot_id, resolved)` to `cards.py` (both feed and
  curations already import from `cards`, avoiding the feed→curations cycle).
- Removed the duplicated `_cover_url` from `feed.py` and `curations.py`; both now
  call `cards.cover_url`. Identical logic — no behavior change.
- Removed feed.py's now-unused `select` / `Spot` imports. Existing feed/curation
  tests still pass.

## Gate (POSTGRES_DB=pictrip_test)
```
alembic upgrade head : at head (0014), no pending ops
ruff check .         : All checks passed!
ruff format --check .: 110 files already formatted
mypy app             : Success: no issues found in 67 source files
pytest -q            : 186 passed in 6.23s
```
Count: 189 → 186 net (added 2 oauth tests + 1 saved-category test = +3; removed
2 dead neighbor test files = −6; net −3). All green.
