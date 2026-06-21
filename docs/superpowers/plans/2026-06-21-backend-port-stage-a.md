# Backend Port — Stage A (port & modify) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the working legacy backend (`~/Desktop/seeeeeeong/PICTRIP/backend`) into the new monorepo skeleton (`~/Desktop/PICTRIP/backend`), then surgically reconcile it to the locked refactor design (S07/S08/S09/S10): denylist auth, OAuth `{provider}`, single Redis pool, curations + new endpoints, canonical-card serialization, additive migrations M1/M2, and authored-but-separately-deployed destructive migrations M3/M4.

**Architecture:** FastAPI modular monolith (`app/modules/`), SQLAlchemy 2.0 async, Postgres + pgvector, Redis, CLIP ViT-B/32. The legacy code is ground truth (S07/S09 reconciled *against* it), so ~70% is reused verbatim; the change surface is auth, OAuth, the Redis pool, four new endpoints, and serialization. **expand→contract**: this plan lands an additive-only image (M1/M2) that becomes the rollback target; M3/M4 (drops) are authored here but applied in a *separate* Stage B deploy.

**Tech Stack:** Python 3.12 · uv · FastAPI · SQLAlchemy 2.0 async · asyncpg · pgvector (`halfvec(512)`, HNSW) · Redis (`redis.asyncio`) · PyJWT[crypto] · CLIP (transformers) · httpx.

**Out of scope (separate follow-on plans):** the `admin` module (A01 Phase 1 read-only + Phase 4 curation editor — net-new, its own spec), all of `mobile/`, `web/` (Cloudflare Pages), and `deploy/monitoring`. The `admin/` skeleton dir is left untouched and unwired in `main.py`.

## Global Constraints

- **Settings module is `app/config.py`** (`Settings(BaseSettings)`, `env_file=".env"`), NOT `app/core/`. `ADMIN_PASSWORD`/`SENTRY_DSN`/KTO/Kakao/Google/Apple keys live here.
- **API base prefix `/v1`** (`settings.API_V1_PREFIX`). `/health` is the only route outside `/v1` (`include_in_schema=False`).
- **JSend everywhere**: `{ data, error, meta }` via `ok()`/`err()` (`app/core/schemas.py`). Errors raise `AppError` subclasses (`app/core/exceptions.py`); the subclass sets HTTP status. Raw dicts bypass the envelope — never return them.
- **Prod DB is at Alembic `head=0010`.** The 10 source revisions (`0001`…`0010`) are ported **verbatim** — never rewrite them. New revisions stack on top: `0011`…`0014`.
- **Embeddings are `halfvec(512)`** (`spot_embeddings.embedding`, `users.taste_vector`). Cast vector literals: `... <=> $1::halfvec(512)`. `hnsw.ef_search = 80` is an asyncpg `server_settings` in `app/core/db.py` — do not add a per-session `SET`.
- **HNSW does not use its index inside JOIN/CTE** (S07 §10): run `ORDER BY embedding <=> $1::halfvec(512) LIMIT N` against the **base `spot_embeddings` table directly**, then join metadata by the returned `content_id`s. Gate with `EXPLAIN` → must show an HNSW Index Scan (not seqscan+sort).
- **`sync_runs` is owned by `pipeline/`** (`CREATE TABLE IF NOT EXISTS` in `pipeline/src/pictrip_data/sync/audit.py`). It must be **excluded from backend Alembic** via `include_object` and never modeled in `Base.metadata`. Backend reads it read-only via raw SQL only (admin plan; not this plan).
- **`backend/` and `pipeline/` are separate Python projects** — no shared venv, no uv workspace.
- **CHECK constraints must be named (`ck_*`)** — autogenerate cannot track anonymous constraints. Partial-index predicates (`postgresql_where`) must be hand-written — autogenerate (#750/#155) drops them.
- **KTO compliance**: never download/store KTO images (URL only, `cpyrhtDivCd Type3`); never persist user-uploaded photo bytes (CLIP runs in memory, bytes discarded); never modify `overview` text (store/display verbatim).
- **Secrets**: `.env` only, never in code or commits. Never copy keys from `~/Documents/Obsidian Vault`.
- **Run all backend Alembic + pytest with `POSTGRES_DB=pictrip_test`** (live `pictrip` rows break global-count asserts).
- **Pre-push gate** (CLAUDE.md): `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && POSTGRES_DB=pictrip_test uv run pytest`. CI (`.github/workflows/backend-ci.yml`) re-runs all of this + `alembic upgrade head`.
- **Commits**: branch `port/backend` off `main`; author as `seeeeeeong` solo — **never add a `Co-Authored-By` trailer.** Commit only the files each task touches.
- **Result module roster = 6**: `users · taste · spots · images · map · system`. `courses` + `recommendations` are deleted.

**Path conventions in this plan:** `SRC/` = `/Users/lee/Desktop/seeeeeeong/PICTRIP/backend`, `DST/` = `/Users/lee/Desktop/PICTRIP/backend`. All work happens in `DST/`.

---

## Task 1: Bulk port — copy legacy backend over the skeleton, reconcile boot files, green baseline

**Files:**
- Create branch `port/backend` in `DST/`.
- Copy: `SRC/app/core/*` → `DST/app/core/` (then merge `exceptions.py`/`schemas.py`/`config.py`), `SRC/app/modules/{users,taste,spots,images,map,system,recommendations,courses}` → `DST/app/modules/`, `SRC/app/main.py`, `SRC/alembic/versions/0001..0010` + `SRC/alembic/env.py` + `SRC/alembic.ini`, `SRC/scripts/*`, `SRC/tests/*`, `SRC/Dockerfile`, `SRC/docker-compose.yml`.
- Merge (do not blind-overwrite): `DST/app/core/exceptions.py`, `DST/app/config.py`, `DST/app/main.py`, `DST/alembic/env.py`, `DST/pyproject.toml`.
- Preserve: `DST/app/modules/admin/**` (untouched), `DST/app/core/schemas.py` if byte-identical to source (else take source).

**Interfaces:**
- Produces: the entire legacy import surface under `DST/app.*` (every symbol in the SRC inventory), Alembic head `0010`, a passing test baseline. All later tasks consume these.

- [ ] **Step 1: Create the working branch**

```bash
cd /Users/lee/Desktop/PICTRIP && git checkout main && git pull --ff-only && git checkout -b port/backend
```

- [ ] **Step 2: Copy code trees (overwrite stubs), excluding venv/caches**

```bash
S=/Users/lee/Desktop/seeeeeeong/PICTRIP/backend
D=/Users/lee/Desktop/PICTRIP/backend
rsync -a --exclude '__pycache__' "$S/app/core/" "$D/app/core/"
rsync -a --exclude '__pycache__' "$S/app/modules/" "$D/app/modules/" --exclude 'admin'
cp "$S/app/main.py" "$D/app/main.py"
cp "$S/app/__init__.py" "$D/app/__init__.py"
cp "$S/alembic.ini" "$D/alembic.ini"
cp "$S/alembic/env.py" "$D/alembic/env.py"
rsync -a --exclude '__pycache__' "$S/alembic/versions/" "$D/alembic/versions/"   # 0001..0010 verbatim
rsync -a --exclude '__pycache__' "$S/scripts/" "$D/scripts/"
rsync -a --exclude '__pycache__' "$S/tests/" "$D/tests/"
cp "$S/Dockerfile" "$D/Dockerfile"
cp "$S/docker-compose.yml" "$D/docker-compose.yml"
```

Confirm `DST/app/modules/admin/` still contains its 6 stub files + `static/README.md` (rsync `--exclude 'admin'` protected it). Confirm `DST/alembic/versions/` now holds exactly 10 files `20260525_0001…20260607_0010`.

- [ ] **Step 3: Merge `exceptions.py` — keep the 3 admin codes**

The source `exceptions.py` has the full 18-code taxonomy but **not** the admin codes. Re-append the target's admin subclasses to the just-copied file so `admin` (future plan) keeps compiling. Append to `DST/app/core/exceptions.py`:

```python
class AdminUnauthorized(AppError):
    code = "ADMIN_UNAUTHORIZED"
    http_status = 401


class AdminHistoryNotFound(AppError):
    code = "ADMIN_HISTORY_NOT_FOUND"
    http_status = 404


class AdminTriggerFailed(AppError):  # Phase 2
    code = "ADMIN_TRIGGER_FAILED"
    http_status = 502
```

- [ ] **Step 4: Merge `config.py` — add `ADMIN_PASSWORD`**

The source `config.py` is the authoritative Settings (JWT/KAKAO/KTO/ANTHROPIC/CLIP/SENTRY fields). Add one field for the future admin plan (harmless now):

```python
    # Admin console (A01 — used by the separate admin plan; required to be set
    # before /admin is wired, otherwise /admin/* returns 503).
    ADMIN_PASSWORD: str | None = None
```

- [ ] **Step 5: Reconcile `alembic/env.py` — exclude pipeline-owned `sync_runs`**

The monorepo invariant forbids backend Alembic from touching `sync_runs`. Add an `include_object` filter so autogenerate never proposes dropping it (it lives in the DB but not in `Base.metadata`). Edit `DST/alembic/env.py`:

```python
def include_object(object_, name, type_, reflected, compare_to):  # noqa: ANN001, ANN201
    # `sync_runs` is owned by pipeline/ (CREATE TABLE IF NOT EXISTS in
    # pictrip_data/sync/audit.py). It is never a backend model; exclude it from
    # autogenerate so a drop is never emitted. (Monorepo invariant, CLAUDE.md.)
    if type_ == "table" and name == "sync_runs":
        return False
    return True
```

Then pass it where `context.configure(...)` is called in both `run_migrations_offline()` and `run_migrations_online()`: add `include_object=include_object` alongside the existing `target_metadata=...`, `compare_type=True`.

- [ ] **Step 6: Merge `pyproject.toml` deps**

Take the union: keep `DST/pyproject.toml`'s `[tool.ruff]`/`[tool.mypy]`/`[tool.pytest]` config and Python `3.12`, and add every runtime + dev dependency the source needs (read `SRC/pyproject.toml`): notably `pyjwt[crypto]`, `httpx`, `transformers`+`torch` (CPU index), `anthropic`, `redis`, `asyncpg`, `pgvector`, `structlog`, `sentry-sdk[fastapi]`, plus dev: `pytest-asyncio`, `fakeredis`, `testcontainers`, `anyio`. Preserve the source's torch CPU `[[tool.uv.index]]` / `[tool.uv.sources]` block verbatim if present. Then:

```bash
cd /Users/lee/Desktop/PICTRIP/backend && uv sync
```

- [ ] **Step 7: Bring up a throwaway test DB and run migrations to head**

```bash
cd /Users/lee/Desktop/PICTRIP/backend
docker compose up -d postgres redis     # local pgvector:pg16 + redis:7-alpine
POSTGRES_DB=pictrip_test uv run alembic upgrade head
POSTGRES_DB=pictrip_test uv run alembic current   # expect 0010 (head)
```
Expected: `upgrade head` runs `0001`→`0010` clean; `current` shows `0010`.

- [ ] **Step 8: Run the ported test suite (baseline green)**

```bash
cd /Users/lee/Desktop/PICTRIP/backend && POSTGRES_DB=pictrip_test uv run pytest -q
```
Expected: PASS (this is legacy code with its legacy tests; courses/recommendations/notifications tests still present and passing — they're removed in Task 3). If `ruff`/`mypy` flag the just-copied code, run `uv run ruff check . && uv run ruff format --check . && uv run mypy app` and fix only mechanical import/format drift introduced by the merge, not behavior.

- [ ] **Step 9: Commit the port**

```bash
git add -A
git commit -m "port(backend): copy legacy backend onto monorepo skeleton, head=0010 green"
```

---

## Task 2: Extract `_seconds_until_kst_midnight` into `app/core/time.py`

The KST-midnight TTL helper currently lives in `recommendations/services.py:40` but is reused by the curation daily cache (Task 10). Move it to core **before** deleting the recommendations module (Task 3).

**Files:**
- Create: `DST/app/core/time.py`
- Create: `DST/tests/test_core_time.py`
- Modify: `DST/app/modules/recommendations/services.py` (import from core instead of defining locally)

**Interfaces:**
- Produces: `app.core.time.seconds_until_kst_midnight(now: datetime) -> int` and `kst_now() -> datetime` and `KST` tzinfo. Consumed by Task 10 (curation cache TTL).

- [ ] **Step 1: Write the failing test**

```python
# DST/tests/test_core_time.py
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.time import KST, seconds_until_kst_midnight


def test_ttl_is_seconds_until_next_kst_midnight():
    now = datetime(2026, 6, 21, 23, 0, 0, tzinfo=KST)  # 23:00 KST → 1h to midnight
    assert seconds_until_kst_midnight(now) == 3600


def test_ttl_never_zero_at_midnight_boundary():
    now = datetime(2026, 6, 21, 0, 0, 0, tzinfo=KST)
    assert seconds_until_kst_midnight(now) == 86400


def test_kst_is_seoul():
    assert KST == ZoneInfo("Asia/Seoul")
```

- [ ] **Step 2: Run it, verify failure**

Run: `POSTGRES_DB=pictrip_test uv run pytest tests/test_core_time.py -q`
Expected: FAIL with `ModuleNotFoundError: app.core.time`.

- [ ] **Step 3: Implement `app/core/time.py`**

```python
"""KST time helpers. Extracted from recommendations (removed in the refactor) so
the curation daily cache can reuse the next-midnight TTL."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def kst_now() -> datetime:
    return datetime.now(tz=KST)


def seconds_until_kst_midnight(now: datetime) -> int:
    """TTL so a cached value expires exactly at the next KST midnight."""
    tomorrow = (now + timedelta(days=1)).date()
    midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=KST)
    return max(1, int((midnight - now).total_seconds()))
```

- [ ] **Step 4: Repoint the (soon-to-be-deleted) recommendations module**

In `DST/app/modules/recommendations/services.py`, delete the local `_KST`/`_seconds_until_kst_midnight` definitions and `from app.core.time import KST as _KST, seconds_until_kst_midnight as _seconds_until_kst_midnight`. (This keeps the suite green until Task 3 removes the module entirely.)

- [ ] **Step 5: Run tests, verify pass**

Run: `POSTGRES_DB=pictrip_test uv run pytest tests/test_core_time.py tests/ -q -k "time or recommend"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/core/time.py tests/test_core_time.py app/modules/recommendations/services.py
git commit -m "refactor(core): extract seconds_until_kst_midnight into app.core.time"
```

---

## Task 3: Remove non-goal modules and routes (courses, recommendations, dead spots/system routes)

**Files:**
- Delete: `DST/app/modules/recommendations/`, `DST/app/modules/courses/`
- Delete: `DST/app/modules/spots/services/trending.py`, `…/related.py`, `…/similar.py`, `…/region.py`, `…/catalog.py`
- Modify: `DST/app/main.py` (drop 2 routers), `DST/app/modules/spots/routes.py` (drop dead routes), `DST/app/modules/spots/services/__init__.py` (drop dead exports), `DST/app/modules/system/routes.py` + `…/services.py` + `…/models.py` (drop notifications/analytics)
- Delete tests: `test_courses*`, `test_recommend*`, `test_spots_trending*`, `test_spots_search*`, `test_spots_related*`, `test_spots_similar*`, `test_spots_by_region*`, `test_spots_moods*`, `test_spots_regions*`, `test_spots_batch*`, `test_system_notifications*`, `test_system_analytics*` (match actual filenames in `DST/tests/`)

**Interfaces:**
- Produces: a 6-module `main.py` router set (`users, taste, spots, images, map, system`). `spots` keeps `detail`, `nearby`, `saved`, `cards`, `rows` services + all ORM models (incl. `SpotConcentration`). `system` keeps only `GET /meta/version`. The `courses`/`notifications`/`analytics_events` **tables remain in the DB** (orphan) until M4 — only their ORM model classes are removed (so Task 21 autogenerate sees them as drops).

- [ ] **Step 1: Delete modules and dead service files**

```bash
cd /Users/lee/Desktop/PICTRIP/backend
git rm -r app/modules/recommendations app/modules/courses
git rm app/modules/spots/services/trending.py app/modules/spots/services/related.py \
       app/modules/spots/services/similar.py app/modules/spots/services/region.py \
       app/modules/spots/services/catalog.py
```

- [ ] **Step 2: Update `main.py` — 6 routers**

Remove the `recommendations_router` and `courses_router` imports and their `app.include_router(...)` lines. The remaining `include_router` set must be exactly: `users_router`, `taste_router`, `spots_router`, `images_router`, `map_router`, `system_router` (each under `settings.API_V1_PREFIX`), plus the root `GET /health`. Do **not** wire `admin` (separate plan).

- [ ] **Step 3: Strip dead routes from `spots/routes.py`**

Remove the handlers + their service calls for: `GET /moods`, `GET /regions`, `GET /moods/{mood_code}/spots`, `GET /spots/trending`, `GET /spots/search`, `GET /spots/by-region`, `GET /spots/batch`, `GET /spots/{content_id}/similar`, `GET /spots/{content_id}/related`. **Keep** `GET /spots/{content_id}` (rebuilt in Task 17). Remove now-dangling imports from `spots/services/__init__.py` (anything re-exported from the deleted service files).

- [ ] **Step 4: Strip notifications/analytics from `system`**

In `system/routes.py` remove `GET/PUT /me/notifications` and `POST /analytics/events`; keep `GET /meta/version`. In `system/services.py` remove `get_notification_prefs`, `update_notification_prefs`, `record_analytics_event`. In `system/models.py` **delete the `Notification` and `AnalyticsEvent` classes** (tables stay orphan in DB; class removal lets Task 21 autogenerate emit the drops). Remove their schemas from `system/schemas.py`.

- [ ] **Step 5: Delete the corresponding tests**

```bash
cd /Users/lee/Desktop/PICTRIP/backend
# list first, then remove the matches that exist:
ls tests | grep -E 'cours|recommend|trending|search|related|similar|by_region|moods|regions|batch|notif|analytic'
git rm tests/<each matched file>
```

- [ ] **Step 6: Verify the suite is green with the reduced surface**

Run: `POSTGRES_DB=pictrip_test uv run pytest -q && uv run mypy app && uv run ruff check .`
Expected: PASS, no import errors, no references to deleted symbols. Fix any straggler import of a removed service/model.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(backend): remove courses/recommendations modules + non-goal routes (6 modules)"
```

---

## Task 4: M1 migration — `curations` + `curation_spots` (+ ORM models)

**Files:**
- Create: `DST/alembic/versions/20260621_0011_curations.py`
- Modify: `DST/app/modules/spots/models.py` (add `Curation`, `CurationSpot`)
- Create: `DST/tests/test_migrations_curations.py`

**Interfaces:**
- Produces: tables `curations`, `curation_spots` per S07 §3.1/§3.2; ORM `Curation`, `CurationSpot`. Consumed by Tasks 9/10 (feed/curation services) and the seed (Task 19).

- [ ] **Step 1: Write the migration (hand-authored — named CHECKs + FK ondelete)**

```python
# DST/alembic/versions/20260621_0011_curations.py
"""curations + curation_spots (M1, additive)

Revision ID: 0011_curations
Revises: 0010_drop_dead_tables
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_curations"
down_revision = "0010_drop_dead_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "curations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=True),
        sa.Column("lead", sa.Text(), nullable=True),
        sa.Column("intro", sa.Text(), nullable=True),
        sa.Column("cover_spot_id", sa.String(32), nullable=True),
        sa.Column("region_cd", sa.String(8), nullable=True),
        sa.Column("mood_id", sa.SmallInteger(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["cover_spot_id"], ["spots.content_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["region_cd"], ["regions.ldong_regn_cd"]),
        sa.ForeignKeyConstraint(["mood_id"], ["moods.id"]),
        sa.CheckConstraint("type IN ('region','mood','editorial')", name="ck_curation_type"),
        sa.CheckConstraint(
            "(type='region' AND region_cd IS NOT NULL) "
            "OR (type='mood' AND mood_id IS NOT NULL) "
            "OR type='editorial'",
            name="ck_curation_scope",
        ),
        sa.UniqueConstraint("slug", name="uq_curations_slug"),
    )
    op.create_index("idx_curations_feed", "curations", ["type", "is_published", "position"])

    op.create_table(
        "curation_spots",
        sa.Column("curation_id", sa.BigInteger(), nullable=False),
        sa.Column("content_id", sa.String(32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["curation_id"], ["curations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["spots.content_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("curation_id", "content_id"),
    )
    op.create_index("idx_curation_spots_order", "curation_spots", ["curation_id", "position"])


def downgrade() -> None:
    op.drop_index("idx_curation_spots_order", table_name="curation_spots")
    op.drop_table("curation_spots")
    op.drop_index("idx_curations_feed", table_name="curations")
    op.drop_table("curations")
```

- [ ] **Step 2: Write the roundtrip test**

```python
# DST/tests/test_migrations_curations.py
import pytest
from sqlalchemy import inspect, text


@pytest.mark.anyio
async def test_curations_tables_and_constraints(db_session):
    insp = await db_session.run_sync(lambda s: inspect(s.bind))
    tables = await db_session.run_sync(lambda s: inspect(s.bind).get_table_names())
    assert {"curations", "curation_spots"} <= set(tables)
    # named CHECKs present
    rows = (await db_session.execute(text(
        "SELECT conname FROM pg_constraint WHERE conrelid='curations'::regclass AND contype='c'"
    ))).scalars().all()
    assert {"ck_curation_type", "ck_curation_scope"} <= set(rows)


@pytest.mark.anyio
async def test_scope_check_rejects_region_without_region_cd(db_session):
    with pytest.raises(Exception):
        await db_session.execute(text(
            "INSERT INTO curations (type, slug, title) VALUES ('region','bad','x')"
        ))
        await db_session.flush()
```

- [ ] **Step 3: Apply + roundtrip the migration, run the test**

```bash
POSTGRES_DB=pictrip_test uv run alembic upgrade head
POSTGRES_DB=pictrip_test uv run alembic downgrade -1
POSTGRES_DB=pictrip_test uv run alembic upgrade head
POSTGRES_DB=pictrip_test uv run pytest tests/test_migrations_curations.py -q
```
Expected: upgrade/downgrade/upgrade clean; tests PASS. Manually eyeball the generated SQL for the two named CHECKs and the three FK `ondelete` clauses.

- [ ] **Step 4: Add ORM models**

In `DST/app/modules/spots/models.py` add (mirroring the migration exactly):

```python
class Curation(Base):
    __tablename__ = "curations"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    subtitle: Mapped[str | None] = mapped_column(Text)
    lead: Mapped[str | None] = mapped_column(Text)
    intro: Mapped[str | None] = mapped_column(Text)
    cover_spot_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("spots.content_id", ondelete="SET NULL"))
    region_cd: Mapped[str | None] = mapped_column(String(8), ForeignKey("regions.ldong_regn_cd"))
    mood_id: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("moods.id"))
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("type IN ('region','mood','editorial')", name="ck_curation_type"),
        CheckConstraint(
            "(type='region' AND region_cd IS NOT NULL) OR (type='mood' AND mood_id IS NOT NULL) OR type='editorial'",
            name="ck_curation_scope",
        ),
    )


class CurationSpot(Base):
    __tablename__ = "curation_spots"
    curation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("curations.id", ondelete="CASCADE"), primary_key=True)
    content_id: Mapped[str] = mapped_column(String(32), ForeignKey("spots.content_id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
```

Add any missing imports (`Identity`, `false`, `CheckConstraint`, `func`) to the file's import block.

- [ ] **Step 5: Confirm model↔DB parity (autogenerate sees no diff)**

```bash
POSTGRES_DB=pictrip_test uv run alembic check || true   # expect only the known trgm GIN false-positive, NOT curations
POSTGRES_DB=pictrip_test uv run pytest tests/test_migrations_curations.py -q && uv run mypy app
```
Expected: no curations-related diff; mypy clean.

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/20260621_0011_curations.py app/modules/spots/models.py tests/test_migrations_curations.py
git commit -m "feat(db): M1 curations + curation_spots (additive, head=0011)"
```

---

## Task 5: M2 migration — `idx_spots_image_pool` partial index

**Files:**
- Create: `DST/alembic/versions/20260622_0012_spots_image_pool_idx.py`
- Modify: `DST/tests/test_migrations_curations.py` (add an index-presence assertion) or a new `test_migrations_image_pool.py`

**Interfaces:**
- Produces: partial index `idx_spots_image_pool (ldong_regn_cd) WHERE show_flag = 1 AND first_image_url IS NOT NULL`. Backs the quality-gate random pool in Task 9.

- [ ] **Step 1: Write the migration (hand-written predicate — autogenerate cannot)**

```python
# DST/alembic/versions/20260622_0012_spots_image_pool_idx.py
"""idx_spots_image_pool partial index (M2, additive)

Revision ID: 0012_spots_image_pool_idx
Revises: 0011_curations
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_spots_image_pool_idx"
down_revision = "0011_curations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_spots_image_pool",
        "spots",
        ["ldong_regn_cd"],
        postgresql_where=sa.text("show_flag = 1 AND first_image_url IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_spots_image_pool", table_name="spots")
```

- [ ] **Step 2: Add the presence test**

```python
# DST/tests/test_migrations_image_pool.py
import pytest
from sqlalchemy import text


@pytest.mark.anyio
async def test_image_pool_partial_index_exists_with_predicate(db_session):
    row = (await db_session.execute(text(
        "SELECT indexdef FROM pg_indexes WHERE indexname='idx_spots_image_pool'"
    ))).scalar_one_or_none()
    assert row is not None
    assert "show_flag = 1" in row and "first_image_url IS NOT NULL" in row
```

- [ ] **Step 3: Apply + roundtrip + test**

```bash
POSTGRES_DB=pictrip_test uv run alembic upgrade head
POSTGRES_DB=pictrip_test uv run alembic downgrade -1
POSTGRES_DB=pictrip_test uv run alembic upgrade head
POSTGRES_DB=pictrip_test uv run pytest tests/test_migrations_image_pool.py -q
```
Expected: clean roundtrip; test PASS (predicate present in `indexdef`).

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/20260622_0012_spots_image_pool_idx.py tests/test_migrations_image_pool.py
git commit -m "feat(db): M2 idx_spots_image_pool partial index (additive, head=0012)"
```

---

## Task 6: Rewrite `auth.py` to the denylist model + rewrite auth tests

Replace the rotation/theft-detection machine (`rt:active`/`sess:`/`user:sessions` ZSET/`rt:grace`/`rt:deny`/`ROTATE_LUA`) with a single `denyjti:{jti}` key, fail-open, no rotation, sliding-exp re-mint, single-flight on the client.

**Files:**
- Modify (rewrite): `DST/app/core/auth.py`
- Modify: `DST/app/modules/users/services.py` (call sites)
- Rewrite: the auth test files (`test_auth_security.py`, `test_auth_token_pair.py`; keep/adapt `test_auth_jwt.py`, `test_auth_exceptions.py`)

**Interfaces:**
- Consumes: `decode_token`, `create_access_token`, `create_refresh_token`, `settings.JWT_*`, `AuthSessionRevoked`/`AuthTokenInvalid`/`AuthTokenExpired`.
- Produces:
  - `mint_token_pair(*, user_id: int, user: UserPublic | None = None) -> TokenPair` (zero Redis writes)
  - `async refresh_tokens(redis: Redis, refresh_token: str) -> TokenPair` (verify + `EXISTS denyjti`, fail-open, sliding re-mint with **same jti**, new `exp=now+30d`)
  - `async deny_refresh(redis: Redis, refresh_token: str | None) -> None` (`SET denyjti:{jti} 1 EX <remaining refresh ttl>`; idempotent, swallows bad tokens)
  - **Removed:** `issue_token_pair`, `rotate_refresh`, `_revoke_family`, `revoke_session`, `revoke_all_user_sessions`, `ROTATE_LUA`. `create_refresh_token` loses its `sid` param.

- [ ] **Step 1: Write the failing tests (denylist behavior)**

```python
# DST/tests/test_auth_denylist.py
import pytest

from app.core.auth import deny_refresh, mint_token_pair, refresh_tokens
from app.core.exceptions import AuthSessionRevoked


@pytest.mark.anyio
async def test_mint_writes_nothing_to_redis(redis_client_fake):
    pair = mint_token_pair(user_id=42)
    assert pair.accessToken and pair.refreshToken
    assert await redis_client_fake.dbsize() == 0  # issuance = zero Redis writes


@pytest.mark.anyio
async def test_refresh_remints_same_jti_with_new_exp(redis_client_fake):
    from app.core.auth import decode_token
    pair = mint_token_pair(user_id=42)
    old_jti = decode_token(pair.refreshToken)["jti"]
    new = await refresh_tokens(redis_client_fake, pair.refreshToken)
    assert decode_token(new.refreshToken)["jti"] == old_jti  # NOT rotated
    assert new.accessToken != pair.accessToken


@pytest.mark.anyio
async def test_denied_refresh_is_rejected(redis_client_fake):
    pair = mint_token_pair(user_id=42)
    await deny_refresh(redis_client_fake, pair.refreshToken)   # logout
    with pytest.raises(AuthSessionRevoked):
        await refresh_tokens(redis_client_fake, pair.refreshToken)


@pytest.mark.anyio
async def test_refresh_fails_open_when_redis_unavailable(monkeypatch, redis_client_fake):
    pair = mint_token_pair(user_id=42)
    async def boom(*a, **k):
        raise ConnectionError("redis down")
    monkeypatch.setattr(redis_client_fake, "exists", boom)
    new = await refresh_tokens(redis_client_fake, pair.refreshToken)  # passes (fail-open)
    assert new.accessToken
```

- [ ] **Step 2: Run, verify failure**

Run: `POSTGRES_DB=pictrip_test uv run pytest tests/test_auth_denylist.py -q`
Expected: FAIL (`ImportError: mint_token_pair`).

- [ ] **Step 3: Rewrite `auth.py`**

Keep `_signing_key`/`_verify_key`/`create_access_token`/`decode_token`/`get_current_user_id`/`CurrentUserId` as-is. Simplify `create_refresh_token` to drop `sid`. Replace everything from `issue_token_pair` onward with:

```python
def create_refresh_token(*, user_id: int, jti: str) -> str:
    key, algo = _signing_key()
    now = datetime.now(tz=UTC)
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.JWT_REFRESH_TOKEN_TTL_SECONDS)).timestamp()),
        "type": "refresh",
    }
    return jwt.encode(payload, key, algorithm=algo)


def mint_token_pair(*, user_id: int, user: UserPublic | None = None) -> TokenPair:
    """Issue a fresh access+refresh pair. Zero Redis writes (denylist model)."""
    from app.modules.users.schemas import TokenPair, UserPublic

    access = create_access_token(user_id=user_id)
    refresh = create_refresh_token(user_id=user_id, jti=str(uuid.uuid4()))
    return TokenPair(
        accessToken=access,
        refreshToken=refresh,
        expiresIn=settings.JWT_ACCESS_TOKEN_TTL_SECONDS,
        user=user or UserPublic(id=user_id, isOnboarded=False),
    )


async def refresh_tokens(redis: Redis, refresh_token: str) -> TokenPair:
    """Sliding refresh, no rotation. Verify sig+exp, check denylist (fail-open),
    re-mint a new access + a refresh with the SAME jti and a fresh 30d exp."""
    from app.modules.users.schemas import TokenPair, UserPublic

    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise AuthTokenInvalid()
    jti = payload.get("jti")
    if not jti:
        raise AuthTokenInvalid()
    try:
        denied = await redis.exists(f"denyjti:{jti}")
    except Exception:  # Redis blip → fail-open (S08: avoid rotation's fail-closed)
        denied = 0
    if denied:
        raise AuthSessionRevoked()

    uid = int(payload["sub"])
    access = create_access_token(user_id=uid)
    refresh = create_refresh_token(user_id=uid, jti=jti)  # same jti, new exp
    return TokenPair(
        accessToken=access,
        refreshToken=refresh,
        expiresIn=settings.JWT_ACCESS_TOKEN_TTL_SECONDS,
        user=UserPublic(id=uid, isOnboarded=False),
    )


async def deny_refresh(redis: Redis, refresh_token: str | None) -> None:
    """Logout/withdraw: add the refresh jti to the denylist for its remaining TTL.
    Idempotent; missing/malformed/expired tokens are silent no-ops."""
    if not refresh_token:
        return
    try:
        payload = decode_token(refresh_token)
    except (AuthTokenInvalid, AuthTokenExpired):
        return
    jti = payload.get("jti")
    if payload.get("type") != "refresh" or not jti:
        return
    ttl = max(1, int(payload["exp"]) - int(time.time()))
    await redis.set(f"denyjti:{jti}", "1", ex=ttl)
```

Remove the now-unused `ROTATE_LUA`, `json` import if unused, and the `SessionStoreUnavailable` `noqa` import if unused.

- [ ] **Step 4: Update call sites in `users/services.py`**

```python
# imports
from app.core.auth import decode_token, deny_refresh, mint_token_pair, refresh_tokens
```
- `authenticate_with_kakao` (and the generalized version in Task 7): replace the final `return await issue_token_pair(redis, user_id=user.id, user=user_public)` with `return mint_token_pair(user_id=user.id, user=user_public)`. This handler no longer needs `redis` — but keep the param until Task 7 finalizes the signature (or drop it now and update the route).
- `refresh_session`: replace `pair = await rotate_refresh(redis, refresh_token)` with `pair = await refresh_tokens(redis, refresh_token)`.
- `logout_session`: replace the body with `await deny_refresh(redis, refresh_token)` (delete the manual decode/`revoke_session`).
- `delete_user_account`: **remove** the `await revoke_all_user_sessions(...)` line. Account safety now rests on `deleted_at` (refresh re-hydrates via `get_user_public`, which raises `AuthTokenInvalid` for a deleted user) + ≤15-min access expiry. Add a one-line comment to that effect.

- [ ] **Step 5: Delete/rewrite obsolete auth tests**

`git rm tests/test_auth_security.py tests/test_auth_token_pair.py` (rotation/family/grace/reuse no longer exist). Keep `test_auth_jwt.py` (token encode/decode) and `test_auth_exceptions.py`. Update any other test that imported the removed symbols.

- [ ] **Step 6: Run the new + adjacent suites**

Run: `POSTGRES_DB=pictrip_test uv run pytest tests/test_auth_denylist.py tests/test_auth_jwt.py tests/ -q -k auth && uv run mypy app`
Expected: PASS, mypy clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(auth): replace rotation machine with denyjti denylist (fail-open, sliding refresh)"
```

---

## Task 7: Generalize OAuth to `/auth/oauth/{provider}` + Google/Apple OIDC

**Files:**
- Create: `DST/app/core/oidc.py` (provider-agnostic verifier; reuses the Kakao JWKS-cache pattern)
- Modify: `DST/app/config.py` (Google client IDs, Apple bundle id/issuer)
- Modify: `DST/app/modules/users/routes.py` (`/auth/oauth/{provider}`)
- Modify: `DST/app/modules/users/services.py` (`authenticate_with_oauth`)
- Modify: `DST/app/modules/users/schemas.py` (rename `KakaoCallbackIn` → `OAuthLoginIn`)
- Create: `DST/tests/test_oauth_providers.py`

**Interfaces:**
- Produces: `app.core.oidc.verify_oauth_id_token(provider: str, id_token: str, *, expected_nonce: str | None) -> OidcClaims` where `OidcClaims = {sub, email, name, picture}`. `provider ∈ {kakao, google, apple}`. Raises `OAuthIdTokenInvalid` / `OAuthProviderUnavailable` / `ValidationFailed` (unknown provider).
- Per-provider rules (S09 §3.1): all verify JWKS signature (kid match), `iss`, `aud`, `exp`, reject `alg:none`. Apple: `iss=https://appleid.apple.com`, `aud=<bundle id>`, `ES256`, `nonce=base64url(sha256(raw))`. Google: `iss∈{accounts.google.com, https://accounts.google.com}`, `aud∈ GOOGLE_CLIENT_IDS`. Kakao: existing `kakao_oidc.verify_id_token` (OIDC issuer). User identity key = `provider + sub`.

- [ ] **Step 1: Write failing tests (use the `kakao_signing_key` RSA fixture; add a Google variant)**

```python
# DST/tests/test_oauth_providers.py
import pytest

from app.core.exceptions import OAuthIdTokenInvalid, ValidationFailed
from app.core.oidc import verify_oauth_id_token


@pytest.mark.anyio
async def test_unknown_provider_rejected():
    with pytest.raises(ValidationFailed):
        await verify_oauth_id_token("myspace", "x.y.z", expected_nonce=None)


@pytest.mark.anyio
async def test_google_bad_audience_rejected(google_id_token_wrong_aud):
    with pytest.raises(OAuthIdTokenInvalid):
        await verify_oauth_id_token("google", google_id_token_wrong_aud, expected_nonce=None)
```

(Add a `google_id_token_wrong_aud` fixture in `conftest.py` minting a token signed by a fake Google JWKS with `aud` outside `GOOGLE_CLIENT_IDS`, mirroring the existing `kakao_signing_key` fixture.)

- [ ] **Step 2: Run, verify failure**

Run: `POSTGRES_DB=pictrip_test uv run pytest tests/test_oauth_providers.py -q`
Expected: FAIL (`ModuleNotFoundError: app.core.oidc`).

- [ ] **Step 3: Add config fields**

In `app/config.py`:
```python
    GOOGLE_CLIENT_IDS: list[str] = []          # iOS/Android/web client_ids accepted as aud
    APPLE_BUNDLE_ID: str | None = None         # aud for Apple id_token
    APPLE_OIDC_ISSUER: str = "https://appleid.apple.com"
    APPLE_JWKS_URL: str = "https://appleid.apple.com/auth/keys"
    GOOGLE_JWKS_URL: str = "https://www.googleapis.com/oauth2/v3/certs"
    GOOGLE_OIDC_ISSUERS: list[str] = ["accounts.google.com", "https://accounts.google.com"]
```

- [ ] **Step 4: Implement `app/core/oidc.py`**

Factor the JWKS fetch/cache + `_jwk_to_pem` helper out of `kakao_oidc.py` (or import them) into a small per-provider verifier. Provide `OidcClaims` dataclass and `verify_oauth_id_token(provider, id_token, *, expected_nonce)` that dispatches:
- `kakao` → delegate to existing `app.core.kakao_oidc.verify_id_token`, map `KakaoClaims` → `OidcClaims`.
- `google` → JWKS from `GOOGLE_JWKS_URL`, `issuer ∈ GOOGLE_OIDC_ISSUERS`, `audience=settings.GOOGLE_CLIENT_IDS`, `algorithms=["RS256"]`.
- `apple` → JWKS from `APPLE_JWKS_URL`, `issuer=APPLE_OIDC_ISSUER`, `audience=APPLE_BUNDLE_ID`, `algorithms=["ES256"]`; if `expected_nonce` given compare against `base64url(sha256(raw_nonce))` (no padding).
- unknown provider → `raise ValidationFailed()`.
Each branch: reject missing `kid`, log only the exception class (no token contents), raise `OAuthIdTokenInvalid` on any `jwt.InvalidTokenError`, `OAuthProviderUnavailable` on JWKS transport failure. Keep the 1h-fresh/24h-stale JWKS cache pattern per provider.

- [ ] **Step 5: Generalize the route + service**

`users/routes.py`: replace `oauth_kakao` with
```python
@router.post("/auth/oauth/{provider}", status_code=status.HTTP_200_OK,
             summary="OIDC id_token → internal token pair")
async def oauth_login(provider: str, body: OAuthLoginIn, session: DbSession) -> dict[str, Any]:
    pair = await services.authenticate_with_oauth(session, provider, body)
    return ok(pair.model_dump())
```
`users/schemas.py`: rename `KakaoCallbackIn` → `OAuthLoginIn` (fields `idToken: str`, `nonce: str | None = None`). `users/services.py`: rename `authenticate_with_kakao` → `authenticate_with_oauth(session, provider, body)`; call `claims = await verify_oauth_id_token(provider, body.idToken, expected_nonce=body.nonce)`; upsert `UserAuthProvider(provider=provider, provider_user_id=claims.sub)`; finish with `mint_token_pair(...)` (no `redis`). Drop the `redis` param from this path.

- [ ] **Step 6: Run tests**

Run: `POSTGRES_DB=pictrip_test uv run pytest tests/test_oauth_providers.py tests/ -q -k "oauth or auth" && uv run mypy app`
Expected: PASS, mypy clean. (Adapt the legacy Kakao login test to the new `/auth/oauth/kakao` path + `OAuthLoginIn`.)

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(auth): generalize OAuth to /auth/oauth/{provider} with kakao/google/apple OIDC"
```

---

## Task 8: Unify the Redis pool (remove `redis_cache` singleton)

**Files:**
- Modify: `DST/app/core/redis.py` (single lifespan pool)
- Modify: `DST/app/main.py` (drop `close_redis(redis_cache)` from lifespan)
- Modify: every consumer of `redis_cache` (`spots/services/detail.py`, `map/services.py` reverse-geocode; `related.py` already deleted)

**Interfaces:**
- Produces: one `get_redis()`/`RedisDep` lifespan pool, `decode_responses=True` (denylist values + cache strings are text; the old binary session payloads are gone). `redis_cache` symbol removed.

- [ ] **Step 1: Rewrite `redis.py` to a single pool**

```python
"""Async Redis: one lifespan-managed pool exposed via get_redis / RedisDep."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from redis.asyncio import Redis, from_url

from app.config import settings

_redis: Redis | None = None


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis client not initialized. Did the lifespan run?")
    return _redis


RedisDep = Annotated[Redis, Depends(get_redis)]


@asynccontextmanager
async def redis_lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _redis
    _redis = from_url(str(settings.REDIS_URL), encoding="utf-8", decode_responses=True, max_connections=50)
    try:
        yield
    finally:
        await _redis.aclose()
        _redis = None
```

- [ ] **Step 2: Repoint consumers + lifespan**

- `main.py` lifespan: remove `from app.core.redis import close_redis` and the `await close_redis()` call (the lifespan context manager now owns teardown). Keep `async with redis_lifespan(app):`.
- `spots/services/detail.py`: the 7-day detail cache used `redis_cache`. Change these functions to accept a `redis: Redis` argument (passed from the route via `RedisDep`) and use it; update the `/spots/{id}` route (Task 17) to inject `RedisDep`. Same for `map/services.py reverse_geocode` (already takes `redis` per inventory — confirm it's `RedisDep`, not `redis_cache`).
- Grep for residual references: `grep -rn redis_cache app/` must return nothing.

- [ ] **Step 3: Verify**

Run: `grep -rn redis_cache app/ ; POSTGRES_DB=pictrip_test uv run pytest -q -k "detail or map or redis" && uv run mypy app`
Expected: no `redis_cache` hits; tests PASS. Update fixtures that injected the old binary pool if needed (the `redis_client_fake` fixture should be `decode_responses=True` now — adjust `conftest.py`).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(redis): collapse redis_cache singleton into one lifespan pool"
```

---

## Task 9: Canonical-card serialization foundation (subtype `category` join + `congestion` enrichment)

Every list/detail endpoint shares the canonical card `{contentId, title, firstImageUrl, category}` where `category = lcls_systm_codes.lcls_systm3_nm` (subtype label), plus optional `congestion` enriched from the preserved `spot_concentration` table. Build this once so Tasks 10–17 consume it.

**Files:**
- Modify: `DST/app/modules/spots/schemas.py` (`SpotCard` core + optional `congestion`)
- Modify/Create: `DST/app/modules/spots/services/cards.py` (add `lcls_systm3_nm` to `SpotCardRow`; add `congestion_for(content_ids)` helper)
- Create: `DST/tests/test_card_serialization.py`

**Interfaces:**
- Produces:
  - `SpotCard` Pydantic shape: `{contentId, title, firstImageUrl: str|None, category: str|None, congestion: "low"|"medium"|"high"|None}` (congestion defaults `None`, omit-friendly).
  - `async load_congestion(session, content_ids: list[str]) -> dict[str, str | None]` — bucket `spot_concentration` rate: `<34→low`, `34–66→medium`, `>66→high`, miss→`None`.
  - `SpotCardRow` gains `lcls_systm3_nm: str | None` (populated by a `LEFT JOIN lcls_systm_codes ON spots.lcls_systm3 = lcls_systm_codes.lcls_systm3_cd`).

- [ ] **Step 1: Write failing tests**

```python
# DST/tests/test_card_serialization.py
import pytest
from app.modules.spots.services.cards import bucket_congestion


def test_congestion_buckets():
    assert bucket_congestion(10) == "low"
    assert bucket_congestion(50) == "medium"
    assert bucket_congestion(90) == "high"
    assert bucket_congestion(None) is None
    assert bucket_congestion(34) == "medium" and bucket_congestion(66) == "medium"
```

- [ ] **Step 2: Run, verify failure**

Run: `POSTGRES_DB=pictrip_test uv run pytest tests/test_card_serialization.py -q`
Expected: FAIL (`ImportError: bucket_congestion`).

- [ ] **Step 3: Implement card helpers**

In `cards.py`:
```python
def bucket_congestion(rate: float | None) -> str | None:
    if rate is None:
        return None
    if rate < 34:
        return "low"
    if rate <= 66:
        return "medium"
    return "high"


async def load_congestion(session, content_ids):
    if not content_ids:
        return {}
    rows = (await session.execute(
        select(SpotConcentration.content_id, SpotConcentration.concentration_rate)
        .where(SpotConcentration.content_id.in_(content_ids))
    )).all()
    return {cid: bucket_congestion(float(rate)) for cid, rate in rows}
```
Add `lcls_systm3_nm` to the `SpotCardRow` dataclass and ensure the base card query in `rows.py` does the `LEFT JOIN lcls_systm_codes`.

- [ ] **Step 4: Update `SpotCard` schema**

In `spots/schemas.py`, make the core card `{contentId, title, firstImageUrl, category, congestion}` with `category: str | None = None` mapped from `lcls_systm3_nm`, and `congestion: Literal["low","medium","high"] | None = None`. Keep the extension fields (`addr1/mapx/mapy/dist/distance/similarity/regionName/sigunguName/overview`) as optional so per-endpoint responses can add them.

- [ ] **Step 5: Run tests + type check**

Run: `POSTGRES_DB=pictrip_test uv run pytest tests/test_card_serialization.py tests/ -q -k "card or saved or detail" && uv run mypy app`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(spots): canonical card with subtype category + congestion enrichment helpers"
```

---

## Task 10: `GET /v1/home/feed` — heroes 6 + rails 3 (quality-gate pool + daily cache)

**Files:**
- Create: `DST/app/modules/spots/services/curations.py`
- Create: `DST/app/modules/spots/services/feed.py`
- Modify: `DST/app/modules/spots/routes.py` (new `/home/feed`), `DST/app/modules/spots/schemas.py` (feed shapes)
- Create: `DST/tests/test_home_feed.py`

**Interfaces:**
- Consumes: `Curation`/`CurationSpot` (Task 4), `idx_spots_image_pool` (Task 5), card helpers (Task 9), `seconds_until_kst_midnight`/`kst_now` (Task 2), `RedisDep` (Task 8).
- Produces: `GET /v1/home/feed` → `{ heroes: [6 × {id, slug, title, subtitle, coverUrl}], rails: [3 × {id, title, subtitle, spots: [≤8 SpotCard]}] }`. Hero `title` keeps `\n` verbatim (client renders `pre-line`). `coverUrl` = cover spot's `firstImageUrl`, else `curation_spots[0]`'s.
- `async resolve_curation_spots(session, redis, curation) -> list[SpotCardRow]`: handpicks from `curation_spots` ordered by `position`; if empty, the **quality-gate random pool** (S07 §3.3): `WHERE show_flag=1 AND first_image_url IS NOT NULL` (+ region_cd or mood_id scope), rank by `(overview present) DESC, (embedding present) DESC`, take top ~30, then deterministic `hash(curation_id + KST-date)` seed → pick/rotate 8. Cache the resolved `content_id` list in `curation:{id}:spots` with TTL = `seconds_until_kst_midnight(kst_now()) + jitter(0..600s)` (jitter = stable function of `curation_id`, not random — avoids a thundering-herd at midnight).

- [ ] **Step 1: Write the failing test (uses a seeded curation)**

```python
# DST/tests/test_home_feed.py
import pytest


@pytest.mark.anyio
async def test_home_feed_shape(client, seed_feed):  # seed_feed: fixture inserting 6 region + 3 mood published curations + a few spots
    r = await client.get("/v1/home/feed")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["heroes"]) == 6
    assert len(data["rails"]) == 3
    assert all({"id", "slug", "title", "subtitle", "coverUrl"} <= h.keys() for h in data["heroes"])
    assert all(len(rail["spots"]) <= 8 for rail in data["rails"])
```

- [ ] **Step 2: Run, verify failure** — Run: `… pytest tests/test_home_feed.py -q` → FAIL (404 / no route).

- [ ] **Step 3: Implement `curations.py` (pool resolution + cache) and `feed.py` (assembly)** per the Interfaces block. Use the HNSW-safe rule only where embeddings are queried; the pool here is a metadata query against `idx_spots_image_pool`. For "embedding present" ranking use `EXISTS (SELECT 1 FROM spot_embeddings e WHERE e.content_id = spots.content_id)`.

- [ ] **Step 4: Add route + schemas**

```python
@router.get("/home/feed", summary="Home feed (6 heroes + 3 rails)")
async def home_feed(session: DbSession, redis: RedisDep) -> dict[str, Any]:
    return ok(await feed.assemble_home_feed(session, redis))
```

- [ ] **Step 5: Run tests + EXPLAIN gate** — Run the feed test; then in `psql` run `EXPLAIN` on the pool query and confirm it uses `idx_spots_image_pool` (not a seq scan). PASS required.

- [ ] **Step 6: Commit** — `git commit -m "feat(spots): GET /home/feed (quality-gate pool, daily cache with jitter)"`

---

## Task 11: `GET /v1/curations/{slug}` (region detail)

**Files:** Modify `spots/routes.py`, `spots/services/curations.py`, `spots/schemas.py`; create `DST/tests/test_curation_detail.py`.

**Interfaces:**
- Produces: `GET /v1/curations/{slug}` → `{id, type, slug, title, lead, intro, coverUrl, spots: [≤8 SpotCard + congestion?]}`. `subtitle` omitted (S09 §5.2). Unpublished/missing → `RESOURCE_NOT_FOUND(404)`. Reuses `resolve_curation_spots`.

- [ ] **Step 1: Failing test** — GET a seeded published region slug → 200 with the shape; GET unknown slug → 404 with `error.code == "RESOURCE_NOT_FOUND"`.
- [ ] **Step 2: Verify failure** (`… pytest tests/test_curation_detail.py -q`).
- [ ] **Step 3: Implement** `get_curation_detail(session, redis, slug)` raising `ResourceNotFound()` when not found or `is_published is False`; serialize per shape.
- [ ] **Step 4: Route** `@router.get("/curations/{slug}")`.
- [ ] **Step 5: Tests pass** + mypy.
- [ ] **Step 6: Commit** — `git commit -m "feat(spots): GET /curations/{slug} region detail"`.

---

## Task 12: `GET /v1/map/regions-tree` (centroid runtime AVG, 24h cache)

**Files:** Modify `map/routes.py`, `map/services.py`, `map/schemas.py`; create `DST/tests/test_regions_tree.py`.

**Interfaces:**
- Consumes: `regions`/`sigungus` tables, `RedisDep`.
- Produces: `GET /v1/map/regions-tree` → `[{regionCode, regionName, centroid:{lat,lng}, sigungus:[{sigunguCode, sigunguName, centroid:{lat,lng}}]}]`. 17 sido + sigungus. **Centroid = runtime AVG** of member spots' `mapx/mapy` (`WHERE show_flag=1`); empty sigungu falls back to its sido's centroid (re-run AVG at `ldong_regn_cd` scope when sigungu AVG is `NULL`). `{시도} 전체` row = sido centroid. Cache whole tree in `regions:tree` for 24h.

- [ ] **Step 1: Failing test** — GET returns a non-empty list; each region has `centroid.lat/lng` floats; sigungus present. (Use a fixture seeding 1 region + 2 sigungus + a few spots with coords.)
- [ ] **Step 2: Verify failure**.
- [ ] **Step 3: Implement** `regions_tree(session, redis)`: try cache; else build via `SELECT AVG(mapx) cx, AVG(mapy) cy FROM spots WHERE ldong_signgu_cd=:s AND show_flag=1` per sigungu, COALESCE to sido AVG when null; cache JSON 24h. Note `mapx`=lng, `mapy`=lat (S07 ERD).
- [ ] **Step 4: Route** `@router.get("/map/regions-tree")`.
- [ ] **Step 5: Tests pass** + mypy.
- [ ] **Step 6: Commit** — `git commit -m "feat(map): GET /map/regions-tree (runtime-AVG centroid, 24h cache)"`.

---

## Task 13: `PUT /v1/users/me/consents` + drop `notification_consent` from the ORM

**Files:** Modify `users/routes.py`, `users/services.py`, `users/schemas.py`, `users/models.py`; create `DST/tests/test_consents.py`.

**Interfaces:**
- Produces: `PUT /v1/users/me/consents` (protected) — body `{locationConsent: bool, photoConsent?: bool, termsVersion: str}` → upsert `user_consents` (PK `user_id`) + `consented_at=now()` → 200 `{locationConsent, photoConsent, termsVersion, consentedAt}`.
- Removes from `UserConsent` model: the `notification_consent` column mapping; removes `get_notification_consent`/`set_notification_consent`/`_get_or_create_consent`'s notification handling. (The DB column is dropped in Task 20 / M3; removing the ORM mapping now makes the Stage-A image stop referencing it — expand/contract.)

- [ ] **Step 1: Failing test** — authenticated PUT with `{locationConsent:true, termsVersion:"v1.0"}` → 200, body echoes values + `consentedAt`; a second PUT updates in place (upsert).
- [ ] **Step 2: Verify failure**.
- [ ] **Step 3: Implement** `put_consents(session, user_id, body)`: `INSERT … ON CONFLICT (user_id) DO UPDATE` (use `pg_insert`); set `consented_at=func.now()`. Add `ConsentIn`/`ConsentOut` schemas. Remove the `notification_consent` mapped column from `UserConsent`; delete the notification consent service funcs (already partially removed in Task 3 if system used them — confirm no caller remains).
- [ ] **Step 4: Route** `@router.put("/users/me/consents")` with `CurrentUserId`.
- [ ] **Step 5: Tests pass** — also run the full `users` suite; mypy clean.
- [ ] **Step 6: Commit** — `git commit -m "feat(users): PUT /users/me/consents; drop notification_consent ORM mapping"`.

---

## Task 14: `GET /v1/users/me` serialization (displayName/avatarUrl) + saved cursor pagination

**Files:** Modify `users/schemas.py` (`UserPublic`, `TokenPair`), `users/services.py` (all `UserPublic(...)` constructions), `users/routes.py` (`/users/me`, `/users/me/saved`), `spots/services/saved.py` (cursor query); create `DST/tests/test_users_me_saved.py`.

**Interfaces:**
- Produces:
  - `UserPublic = {id, displayName: str|None, email: str|None, avatarUrl: str|None, isOnboarded: bool, createdAt: datetime|None}` — **serialization rename only** (`users.name`→`displayName`, `users.profile_image_url`→`avatarUrl`); DB columns unchanged.
  - `GET /v1/users/me/saved?cursor=&limit=` — `limit` default 24 (1–60); `data = [SpotCard core]`; `meta.pagination = {nextCursor, hasMore, count}`; `nextCursor = base64(created_at,content_id)` opaque; sort `user_saved_spots.created_at DESC`.

- [ ] **Step 1: Failing tests**
```python
@pytest.mark.anyio
async def test_me_uses_displayName_avatarUrl(client, auth_headers):
    r = await client.get("/v1/users/me", headers=auth_headers)
    body = r.json()["data"]
    assert "displayName" in body and "avatarUrl" in body
    assert "name" not in body and "profileImageUrl" not in body

@pytest.mark.anyio
async def test_saved_paginates_with_cursor(client, auth_headers, many_saved):  # >24 saved
    r1 = await client.get("/v1/users/me/saved?limit=24", headers=auth_headers)
    meta = r1.json()["meta"]["pagination"]
    assert meta["hasMore"] is True and meta["nextCursor"]
    r2 = await client.get(f"/v1/users/me/saved?limit=24&cursor={meta['nextCursor']}", headers=auth_headers)
    assert r2.status_code == 200
```
- [ ] **Step 2: Verify failure**.
- [ ] **Step 3: Implement** — Rename `UserPublic` fields (update every construction in `users/services.py` and `app/core/auth.py`'s minimal `UserPublic(id=…, isOnboarded=…)`). Add cursor encode/decode helpers; rewrite `list_saved_spots` to take `cursor`/`limit`, return `(rows, next_cursor, has_more)`. Update the `/users/me/saved` route to pass `pagination=` into `ok(...)` and serialize cards via the canonical `SpotCard`.
- [ ] **Step 4: Run** the users suite + mypy. Update legacy saved tests that asserted the flat `limit=100` shape.
- [ ] **Step 5: Commit** — `git commit -m "feat(users): displayName/avatarUrl serialization + saved cursor pagination"`.

---

## Task 15: Reconstruct `POST /v1/taste/photo-search`

**Files:** Modify `taste/routes.py`, `taste/services.py`, `taste/schemas.py`; modify `images/services.py` only if the neighbor query needs the HNSW-direct shape; create `DST/tests/test_photo_search.py`.

**Interfaces:**
- Produces: `POST /v1/taste/photo-search` — **multipart** `image` + query `lat?`/`lng?` → `{matches: [SpotCard + {similarity: float, distance?: float, regionName?, sigunguName?, congestion?}], queryHadLocation: bool}`. Threshold = **calibrated** (config `PHOTO_SEARCH_SIMILARITY_FLOOR`, default 0.60 but tunable) with a **top-N soft floor** so a sparse result set isn't empty; cap ≤30, sorted by `similarity` desc; soft-floor still empty → normal empty `200`. CLIP bytes discarded after embedding (KTO). `PhotoSearchResult{detectedMoods}` shape removed.
- HNSW rule (S07 §10): `SELECT content_id FROM spot_embeddings ORDER BY embedding <=> $1::halfvec(512) LIMIT 30` on the base table; join metadata + distance afterward by id.

- [ ] **Step 1: Failing test** — POST a small JPEG (no lat/lng) → 200, `queryHadLocation is False`, `matches` is a list of cards each with `similarity`; with lat/lng → cards include `distance`. (Stub the embedder in the fixture to return a fixed vector so neighbors are deterministic against seeded embeddings.)
- [ ] **Step 2: Verify failure**.
- [ ] **Step 3: Implement** the multipart handler (`image: UploadFile`, `lat: float | None = Query(None)`, `lng: float | None`), embed in memory, neighbor query (HNSW-direct), apply calibrated floor + soft top-N, enrich cards (category subtype via Task 9, congestion, region meta, distance when lat/lng). Add `PHOTO_SEARCH_SIMILARITY_FLOOR: float = 0.60` and `PHOTO_SEARCH_MAX: int = 30` to config.
- [ ] **Step 4: EXPLAIN gate** — confirm the neighbor query shows an HNSW Index Scan; measure `count(embedding)::float/count(*)` coverage (backfill gate, S10 §4) and log it.
- [ ] **Step 5: Tests pass** + mypy. Remove the old `SimilarNeighbor`/`PhotoSearchResult` schemas.
- [ ] **Step 6: Commit** — `git commit -m "feat(taste): photo-search multipart + calibrated floor + congestion (HNSW-direct)"`.

---

## Task 16: Reconstruct `GET /v1/map/nearby`

**Files:** Modify `map/routes.py`, `map/services.py`, `map/schemas.py`; create/extend `DST/tests/test_map_nearby.py`.

**Interfaces:**
- Produces: `GET /v1/map/nearby?lat&lng&radius&category` — `radius` default **3000** (1000→3000); response `[SpotCard + {addr1, mapx, mapy, dist, regionName?, sigunguName?, overview?, congestion?}]`, distance-sorted, cap **30**. **Drop** the Redis `crowd` merge and `firstImage2Url`; **add** `congestion` (from `spot_concentration` JOIN, Task 9) and subtype `category`. Coarse chip buckets (`NearbyCategory`: attraction/food/cafe/leisure/shopping) unchanged. `lat`/`lng` missing → `VALIDATION_FAILED(422)`; empty = normal `[]`.

- [ ] **Step 1: Failing tests** — default radius is 3000 (assert via a spot just outside 1km but inside 3km appears); response cards have no `crowd`/`firstImage2Url`, have `congestion` key (null when no concentration row), `category` is the subtype label.
- [ ] **Step 2: Verify failure**.
- [ ] **Step 3: Implement** — set `radius: int = Query(3000)`, remove crowd merge from `nearby_spots` (drop the `redis` crowd call), add congestion enrichment + region meta + subtype category. Keep the existing bbox+haversine query and `category_predicate`.
- [ ] **Step 4: Tests pass** + mypy. Update legacy nearby tests asserting crowd/firstImage2Url.
- [ ] **Step 5: Commit** — `git commit -m "feat(map): nearby radius 3000, drop crowd, add congestion + subtype category"`.

---

## Task 17: Reconstruct `GET /v1/spots/{contentId}` (detail)

**Files:** Modify `spots/routes.py`, `spots/services/detail.py`, `spots/schemas.py`; extend `DST/tests/test_spots_detail.py`.

**Interfaces:**
- Produces: `GET /v1/spots/{contentId}` → `SpotCard core + {addr1, addr2?, mapx, mapy, overview, homepage?, tel?, regionName?, sigunguName?, congestion?, detailStatus: "fresh"|"stale"|"unavailable", images: [{originImageUrl, smallImageUrl?}], intro: {usetime?, restdate?, parking?, infocenter?, firstmenu?, treatmenu?} | null}`. **Drop `moods[]`**. Lazy KTO enrich failure → `200` with `detailStatus="unavailable"` (not an error). Missing → `RESOURCE_NOT_FOUND(404)`. Inject `RedisDep` for the 7-day cache (Task 8).

- [ ] **Step 1: Failing tests** — response has no `moods`; has `detailStatus`; has `congestion` key; 404 for unknown id. Keep the existing lazy-cache test, adapted to `RedisDep`.
- [ ] **Step 2: Verify failure**.
- [ ] **Step 3: Implement** — remove `moods[]` from the serializer + query; add congestion (Task 9) + region meta; thread `redis` through `load_spot_detail`. Keep overview verbatim, `intro_data` firstmenu/treatmenu mapping, image strip.
- [ ] **Step 4: Tests pass** + mypy.
- [ ] **Step 5: Commit** — `git commit -m "feat(spots): spot detail drops moods[], adds congestion + region meta (RedisDep cache)"`.

---

## Task 18: Compose Redis persistence/eviction flags + verify `include_object`

**Files:** Modify `DST/docker-compose.yml` (local), `/Users/lee/Desktop/PICTRIP/deploy/api-host/docker-compose.yml` (prod). Verify `DST/alembic/env.py` `include_object` (added in Task 1).

**Interfaces:** Produces hardened Redis (AOF everysec + 256mb noeviction). No code surface.

- [ ] **Step 1: Update both compose Redis commands** to: `redis-server --save 60 1 --appendonly yes --appendfsync everysec --maxmemory 256mb --maxmemory-policy noeviction --loglevel warning`.
- [ ] **Step 2: Confirm the env.py filter** — `grep -n "sync_runs" alembic/env.py` shows the `include_object` guard; `POSTGRES_DB=pictrip_test uv run alembic check` does not propose dropping `sync_runs` (manually create it first: `psql -c "CREATE TABLE IF NOT EXISTS sync_runs(id bigint primary key)"` on `pictrip_test`, then `alembic check`, then drop it).
- [ ] **Step 3: Boot smoke** — `docker compose up -d` then `curl -s localhost:8000/health` → `{"status":"ok"}` (envelope-free root route). `redis-cli config get appendonly` → `yes`.
- [ ] **Step 4: Commit** — `git commit -m "chore(infra): Redis AOF everysec + 256mb noeviction; confirm sync_runs excluded from Alembic"`.

---

## Task 19: Seed script — 6 region + 3 mood curations

**Files:** Create `DST/scripts/seed_curations.py`; create `DST/tests/test_seed_curations.py`.

**Interfaces:**
- Produces: idempotent seeding of 6 region + 3 mood curations: `slug`, `title` (hero copy **verbatim** from `docs/mockups/05-home.html` / S02 hero registry, `\n` preserved), `subtitle`/`lead`/`intro`, `cover_spot_id` (a valid spot), `region_cd`/`mood_id` scope, `is_published=true`, `position`. Handpicks left **empty** (random pool operates until handpicks are loaded later — data only, no migration). Follows the `scripts/sync_concentration.py` convention (`async_session_factory`, `argparse --dry-run`, `ON CONFLICT (slug) DO NOTHING`).

- [ ] **Step 1: Failing test** — run `seed_curations.main()` against `pictrip_test`, then assert 6 `type='region'` + 3 `type='mood'` published rows exist and each satisfies `ck_curation_scope`; a second run inserts nothing (idempotent).
- [ ] **Step 2: Verify failure**.
- [ ] **Step 3: Implement** the seeder. Pull the 6 hero titles/subtitles verbatim from the mockup registry; pick `region_cd` for each region curation and `mood_id` for each mood curation (must be non-null to satisfy `ck_curation_scope`). Set `cover_spot_id` to any existing published spot in scope (nullable if none — falls back to `curation_spots[0]`, which is empty initially → cover resolves null, client shows inset-gray).
- [ ] **Step 4: Tests pass**; then `/home/feed` returns non-empty heroes/rails against a seeded test DB (re-run `tests/test_home_feed.py`).
- [ ] **Step 5: Commit** — `git commit -m "feat(scripts): seed_curations (6 region + 3 mood, idempotent)"`.

---

## Task 20: M3 migration — drop dead columns (Stage B, authored now)

> **Deploy gate:** M3/M4 are authored in this branch but applied in a *separate* Stage B deploy, after the additive image (Tasks 1–19) is live and is the rollback target (S10 §3.1). The ORM already stopped referencing these columns (Tasks 6, 13).

**Files:** Create `DST/alembic/versions/20260623_0013_drop_dead_columns.py`; extend a migration test.

**Interfaces:** Produces drop of `user_auth_providers.refresh_token_enc` and `user_consents.notification_consent`.

- [ ] **Step 1: Write the migration**
```python
revision = "0013_drop_dead_columns"
down_revision = "0012_spots_image_pool_idx"

def upgrade() -> None:
    op.drop_column("user_auth_providers", "refresh_token_enc")
    op.drop_column("user_consents", "notification_consent")

def downgrade() -> None:
    op.add_column("user_consents", sa.Column("notification_consent", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("user_auth_providers", sa.Column("refresh_token_enc", sa.Text(), nullable=True))
```
- [ ] **Step 2: Roundtrip** — `alembic upgrade head` → `downgrade -1` → `upgrade head` clean on `pictrip_test`.
- [ ] **Step 3: Test** — assert `refresh_token_enc`/`notification_consent` absent from `information_schema.columns` after upgrade.
- [ ] **Step 4: Commit** — `git commit -m "feat(db): M3 drop refresh_token_enc + notification_consent (Stage B, head=0013)"`.

---

## Task 21: M4 migration — drop non-goal tables (Stage B, authored now)

**Files:** Create `DST/alembic/versions/20260623_0014_drop_nongoal_tables.py`; extend a migration test.

**Interfaces:** Produces drop of `course_items`→`course_days`→`courses` (child→parent), `notifications`, `analytics_events`. **`spot_concentration` is preserved** (congestion source).

- [ ] **Step 1: Write the migration** — drops in child→parent order; `downgrade` recreates parent→child with the original columns/FKs (reference the `0004` definitions for exact column DDL). Review autogenerate's output if used and remove any duplicate `drop_index`. Do **not** reference `spot_concentration`.
- [ ] **Step 2: Roundtrip** on `pictrip_test` (upgrade/downgrade/upgrade clean).
- [ ] **Step 3: Test** — after upgrade, `courses/course_days/course_items/notifications/analytics_events` absent; `spot_concentration` **present**.
- [ ] **Step 4: Commit** — `git commit -m "feat(db): M4 drop courses/notifications/analytics tables, preserve spot_concentration (Stage B, head=0014)"`.

---

## Task 22: Full verification + PR

**Files:** none (gates + PR).

- [ ] **Step 1: Full backend gate**
```bash
cd /Users/lee/Desktop/PICTRIP/backend
uv run ruff check . && uv run ruff format --check . && uv run mypy app && \
POSTGRES_DB=pictrip_test uv run pytest -q
```
Expected: all green.
- [ ] **Step 2: Migration roundtrip to head 0014** — `POSTGRES_DB=pictrip_test uv run alembic upgrade head` then `downgrade base` then `upgrade head` on a fresh `pictrip_test` — clean both ways. Confirm `alembic current` = `0014`.
- [ ] **Step 3: Boot + public-shape smoke** — `docker compose up -d`; `curl -s localhost:8000/health`; `curl -s localhost:8000/v1/home/feed | jq '.data.heroes|length'` (6 after seeding); confirm removed endpoints 404 (`/v1/spots/trending`, `/v1/recommendations/today-inspo`, `/v1/courses`).
- [ ] **Step 4: Push + open PR** filling `.github/pull_request_template.md` (required checklist): tick `backend`; verification section confirms ruff/format/mypy/pytest green and **"DB 변경: 마이그레이션 SQL 리뷰 완료 (부분/CHECK 인덱스 수동 확인 · sync_runs 미포함)"**; record load-bearing decisions (denylist auth, sliding refresh, congestion re-fusion, expand/contract M3/M4 deferred to Stage B). No `Co-Authored-By` trailer.
```bash
git push -u origin port/backend
gh pr create --fill --base main
```

---

## Self-Review (spec coverage)

- **S10 §3.2 Stage A items** → auth denylist (T6), OAuth `{provider}` (T7), Redis pool unify (T8), new endpoints feed/curation/regions-tree/consents (T10–13), serialization renames + photo-search + nearby + detail + card category/congestion (T9, T14–17), route/module removal (T3), compose flags (T18), `_seconds_until_kst_midnight` extraction (T2). ✓
- **S10 §2 migrations** → M1 (T4), M2 (T5), M3 (T20), M4 (T21); seed (T19). ✓
- **S07 DDL** (named CHECKs `ck_curation_type`/`ck_curation_scope`, FK ondelete, partial index predicate, ERD parity) → T4/T5. ✓
- **S09 contract** (canonical card, congestion field, displayName/avatarUrl, saved cursor, photo-search shape, nearby radius/congestion, detail moods[] removal, removed routes) → T9/T13–17/T3. ✓
- **Monorepo invariants** (sync_runs excluded, separate projects, admin untouched) → T1 (include_object), scope note. ✓
- **expand→contract** (M3/M4 authored, deployed separately) → T20/T21 deploy-gate notes. ✓
- **Deferred (flagged, not silently dropped):** admin module A01 (separate plan), mobile/web/CF Pages, the actual Stage B/prod deploy execution, handpick-spot loading (data-only, post-seed). The `congestion` calibration thresholds and photo-search similarity floor are config-tunable, not hardcoded design.

---

**Plan complete and saved to `docs/superpowers/plans/2026-06-21-backend-port-stage-a.md`.**
