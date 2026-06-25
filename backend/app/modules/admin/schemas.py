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
    source: CollectionSource
    nextScheduledAt: datetime | None


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
