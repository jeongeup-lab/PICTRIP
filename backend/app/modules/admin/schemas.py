"""admin schemas — JSend `data` payloads (A01 §3).

Field names are the contract (camelCase) — they must match A01 §3 exactly because
the static admin pages read ``data.<field>`` directly. These DTOs carry no ORM
imports (Pydantic only).
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.kto_images import https_kto_image


# --- GET /admin/api/collection -------------------------------------------------
class LastRun(BaseModel):
    status: str | None
    finishedAt: datetime | None
    ranAt: datetime
    apiCalls: int
    inserted: int
    updated: int
    softDeleted: int
    durationSec: float | None


class CollectionSource(BaseModel):
    name: str
    endpoint: str
    lastRun: LastRun | None


class CollectionStatus(BaseModel):
    totalSpots: int
    embeddedSpots: int
    source: CollectionSource
    nextScheduledAt: datetime | None


# --- POST /admin/api/collection/trigger (A01 §3 / ADM-009) --------------------
class TriggerResult(BaseModel):
    """Result of a collection trigger. ``runId`` is None for workflow_dispatch
    (GitHub returns 204 with no run id; the admin polls sync_runs for status)."""

    job: str
    runId: str | None
    accepted: bool


# --- GET /admin/api/embedding -------------------------------------------------
class EmbeddingRecent(BaseModel):
    """The embedding state of spots from the latest collection run (synced since
    ``since``). ``outstanding`` = target - embedded (still need embedding)."""

    since: datetime | None
    target: int
    embedded: int
    outstanding: int


class EmbeddingStatus(BaseModel):
    totalSpots: int
    withImage: int  # image-bearing spots = the coverage denominator
    embedded: int  # image-bearing spots that have an embedding
    missing: int  # withImage - embedded (all-time backlog)
    failed: int  # spots in embedding_failures (recorded failures)
    pending: int  # missing - failed (never attempted)
    failuresByReason: dict[str, int]
    recent: EmbeddingRecent
    lastComputedAt: datetime | None
    running: bool  # an embed job currently holds the Redis lock


# --- POST /admin/api/embedding/trigger ----------------------------------------
class EmbeddingTriggerResult(BaseModel):
    job: str  # "embed-failed" | "embed-missing"
    scope: str  # "failed" | "missing"
    accepted: bool


# --- GET /admin/api/history?days=N --------------------------------------------
class HistoryDay(BaseModel):
    date: date
    success: int
    error: int
    running: int
    runs: int


class HistoryList(BaseModel):
    days: list[HistoryDay]


# --- GET /admin/api/history/{date} --------------------------------------------
class HistoryRun(BaseModel):
    id: int
    status: str
    mode: str
    startedAt: datetime
    finishedAt: datetime | None
    apiCalls: int
    inserted: int
    updated: int
    softDeleted: int
    durationSec: float | None
    error: str | None


class HistoryDetail(BaseModel):
    date: str
    runs: list[HistoryRun]


# --- GET /admin/api/health ----------------------------------------------------
class HealthApi(BaseModel):
    version: str
    uptimeSec: int
    p95Ms: float | None


class HealthDb(BaseModel):
    ok: bool
    poolInUse: int
    poolSize: int
    spots: int


class HealthTunnel(BaseModel):
    ok: bool | None
    detail: str | None


class HealthUsers(BaseModel):
    total: int
    active: int
    new7d: int
    deleted30d: int
    kakao: int


class Health(BaseModel):
    api: HealthApi
    db: HealthDb
    tunnel: HealthTunnel
    users: HealthUsers


# --- curation editor (A01 §7 / ADM-012~015) -----------------------------------
# All field names are camelCase contract — the static curation.html reads
# ``data.<field>`` directly. Scoped writes to curations/curation_spots only.


class CurationListItem(BaseModel):
    id: int
    type: str
    slug: str
    title: str
    subtitle: str | None
    coverUrl: str | None
    position: int

    # KTO firstimage URLs arrive as http://; the admin HTML CSP only allows
    # https: images, so upgrade the transport (same URL, no download).
    @field_validator("coverUrl")
    @classmethod
    def _upgrade_cover(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class CurationList(BaseModel):
    """GET /admin/api/curations — grouped by type, each ordered by position.

    The board is always the fixed seeded hero 6 + mood rails 3; legacy
    ``editorial`` rows are ignored (no group for them).
    """

    heroes: list[CurationListItem]  # type='region'
    rails: list[CurationListItem]  # type='mood'


class CoverSpot(BaseModel):
    contentId: str
    name: str
    imageUrl: str | None

    @field_validator("imageUrl")
    @classmethod
    def _upgrade_image(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class Handpick(BaseModel):
    contentId: str
    name: str
    category: str | None
    imageUrl: str | None
    position: int

    @field_validator("imageUrl")
    @classmethod
    def _upgrade_image(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class CurationDetail(BaseModel):
    """GET /admin/api/curations/{id} — copy + cover + handpicks."""

    id: int
    type: str
    slug: str
    title: str
    subtitle: str | None
    lead: str | None
    intro: str | None
    coverSpot: CoverSpot | None
    regionCd: str | None
    moodId: int | None
    position: int
    handpicks: list[Handpick]


class PreviewSpot(BaseModel):
    """One resolved display spot for the editor preview (handpick or auto-fill)."""

    contentId: str
    name: str
    category: str | None
    imageUrl: str | None

    @field_validator("imageUrl")
    @classmethod
    def _upgrade_image(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class CurationPreview(BaseModel):
    """GET /admin/api/curations/{id}/preview — spots the app would actually show.

    Handpicked spots if any, else the quality-gate auto-fill pool (the same
    resolver the live home feed uses) so the editor can preview empty curations
    truthfully instead of showing placeholders.
    """

    spots: list[PreviewSpot]


class CurationUpdate(BaseModel):
    """PUT /admin/api/curations/{id} body — only copy/cover.

    type/slug/region_cd/mood_id are NOT editable here (the ck_curation_scope
    invariant stays satisfied because type/scope are unchanged). Ordering moved
    to the atomic PUT /admin/api/curations/positions. A cached browser copy of
    the old UI may still send legacy ``isPublished``/``position`` keys, so extra
    fields must be ignored (never 422, never applied).
    """

    model_config = ConfigDict(extra="ignore")

    title: str
    subtitle: str | None = None
    lead: str | None = None
    intro: str | None = None
    coverSpotId: str | None = None


class PositionsUpdate(BaseModel):
    """PUT /admin/api/curations/positions body — atomic per-type reorder.

    ``orderedIds`` must be a permutation of ALL curation ids of ``type``
    (validated in the service); position = array index, applied in one
    transaction.
    """

    type: str  # "region" | "mood" (validated in the service → ADMIN_VALIDATION)
    orderedIds: list[int]


class SpotsUpdate(BaseModel):
    """PUT /admin/api/curations/{id}/spots body — replace handpicks (≤8)."""

    spotIds: list[str]


class HandpickList(BaseModel):
    handpicks: list[Handpick]


# --- admin spot picker (A01 §7 / ADM-015) -------------------------------------
class SpotSearchItem(BaseModel):
    contentId: str
    name: str
    regionCd: str | None
    regionName: str | None
    imageUrl: str | None

    @field_validator("imageUrl")
    @classmethod
    def _upgrade_image(cls, v: str | None) -> str | None:
        return https_kto_image(v)


class SpotSearchResult(BaseModel):
    """GET /admin/api/spots/search — one page (20) + pagination meta."""

    spots: list[SpotSearchItem]
    total: int  # all rows matching the filters, not just this page
    hasMore: bool  # offset + len(spots) < total


# --- 게시물(해외 스팟) 숨김 관리 (A7) — scoped write: overseas_spots.is_hidden ---
class OverseasListItem(BaseModel):
    """One row of the 게시물 관리 table. image_url is a Wikimedia Commons https
    URL already (no KTO http→https upgrade needed)."""

    id: int
    nameKo: str
    countryNameKo: str
    imageUrl: str
    fameScore: int
    isHidden: bool


class OverseasList(BaseModel):
    """GET /admin/api/overseas — id-cursor page. ``nextCursor`` is the last id
    of this page when more rows follow, else None."""

    items: list[OverseasListItem]
    nextCursor: int | None


class OverseasVisibilityUpdate(BaseModel):
    """PUT /admin/api/overseas/{id}/visibility body."""

    isHidden: bool


class OverseasVisibility(BaseModel):
    id: int
    isHidden: bool
