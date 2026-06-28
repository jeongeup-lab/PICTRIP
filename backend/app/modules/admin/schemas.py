"""admin schemas — JSend `data` payloads (A01 §3).

Field names are the contract (camelCase) — they must match A01 §3 exactly because
the static admin pages read ``data.<field>`` directly. These DTOs carry no ORM
imports (Pydantic only).
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


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
    isPublished: bool
    position: int


class CurationList(BaseModel):
    """GET /admin/api/curations — grouped by type, each ordered by position."""

    heroes: list[CurationListItem]  # type='region'
    rails: list[CurationListItem]  # type='mood'
    editorial: list[CurationListItem]  # type='editorial'


class CoverSpot(BaseModel):
    contentId: str
    name: str
    imageUrl: str | None


class Handpick(BaseModel):
    contentId: str
    name: str
    category: str | None
    imageUrl: str | None
    position: int


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
    isPublished: bool
    position: int
    handpicks: list[Handpick]


class CurationUpdate(BaseModel):
    """PUT /admin/api/curations/{id} body — only copy/cover/publish/position.

    type/slug/region_cd/mood_id are NOT editable here (the ck_curation_scope
    invariant stays satisfied because type/scope are unchanged).
    """

    title: str
    subtitle: str | None = None
    lead: str | None = None
    intro: str | None = None
    coverSpotId: str | None = None
    isPublished: bool
    position: int


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


class SpotSearchResult(BaseModel):
    spots: list[SpotSearchItem]
