"""admin schemas — JSend `data` payloads (A01 §3).

Field names are the contract (camelCase) — they must match A01 §3 exactly because
the static admin pages read ``data.<field>`` directly. These DTOs carry no ORM
imports (Pydantic only).
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


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


class TriggerResult(BaseModel):
    """Result of a collection trigger. ``runId`` is None for workflow_dispatch
    (GitHub returns 204 with no run id; the admin polls sync_runs for status)."""

    job: str
    runId: str | None
    accepted: bool


class EmbeddingRecent(BaseModel):
    """The embedding state of spots from the latest collection run (synced since
    ``since``). ``outstanding`` = target - embedded (still need embedding)."""

    since: datetime | None
    target: int
    embedded: int
    outstanding: int


class EmbeddingStatus(BaseModel):
    totalSpots: int
    withImage: int
    embedded: int
    missing: int
    failed: int
    pending: int
    failuresByReason: dict[str, int]
    recent: EmbeddingRecent
    lastComputedAt: datetime | None
    running: bool


class EmbeddingTriggerResult(BaseModel):
    job: str
    scope: str
    accepted: bool


class HistoryDay(BaseModel):
    date: date
    success: int
    error: int
    running: int
    runs: int


class HistoryList(BaseModel):
    days: list[HistoryDay]


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
