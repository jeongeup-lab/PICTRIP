"""admin services — read-only aggregation + health probes (A01 §2/§3).

Transaction-free (read-only). Calls :mod:`repositories`, shapes rows into the
§3 DTOs. No HTTP concerns (routes wrap the DTO in the JSend envelope).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import engine
from app.core.exceptions import AdminHistoryNotFound
from app.core.version import API_VERSION, uptime_seconds
from app.modules.admin import repositories as repo
from app.modules.admin.schemas import (
    CollectionSource,
    CollectionStatus,
    Health,
    HealthApi,
    HealthDb,
    HealthTunnel,
    HealthUsers,
    HistoryDay,
    HistoryDetail,
    HistoryList,
    HistoryRun,
    LastRun,
)

_SOURCE_NAME = "국문 관광정보 서비스"
_SOURCE_ENDPOINT = "areaBasedSyncList2"


async def get_collection_status(session: AsyncSession) -> CollectionStatus:
    total = await repo.count_spots(session)
    row = await repo.latest_sync_run(session)

    last_run: LastRun | None = None
    if row is not None:
        last_run = LastRun(
            status=row.status,
            finishedAt=row.finished_at,
            # ranAt = finished_at when present, else started_at (A01 §2.1).
            ranAt=row.finished_at or row.started_at,
            apiCalls=row.api_calls,
            inserted=row.inserted,
            updated=row.updated,
            softDeleted=row.soft_deleted,
            durationSec=row.duration_sec,
        )

    return CollectionStatus(
        totalSpots=total,
        source=CollectionSource(
            name=_SOURCE_NAME,
            endpoint=_SOURCE_ENDPOINT,
            lastRun=last_run,
        ),
        # Honest null: no scheduler metadata is wired yet (A01 §2.1 allows it).
        nextScheduledAt=None,
    )


async def get_history(session: AsyncSession, days: int) -> HistoryList:
    rows = await repo.sync_run_daily_counts(session, days)
    return HistoryList(
        days=[
            HistoryDay(
                date=r.day,
                success=r.success,
                error=r.error,
                running=r.running,
                runs=r.runs,
            )
            for r in rows
        ]
    )


async def get_history_detail(session: AsyncSession, day: date) -> HistoryDetail:
    rows = await repo.sync_runs_on_date(session, day)
    if not rows:
        raise AdminHistoryNotFound
    return HistoryDetail(
        date=day.isoformat(),
        runs=[
            HistoryRun(
                id=r.id,
                status=r.status,
                mode=r.mode,
                startedAt=r.started_at,
                finishedAt=r.finished_at,
                apiCalls=r.api_calls,
                inserted=r.inserted,
                updated=r.updated,
                softDeleted=r.soft_deleted,
                durationSec=r.duration_sec,
                error=r.error,
            )
            for r in rows
        ],
    )


def _pool_stats() -> tuple[int, int]:
    """(poolInUse, poolSize) from the live serving engine.

    Read from the module-level ``engine`` (the real QueuePool), not the request
    session — that's the pool the spec's ``poolSize=20`` refers to. Guarded with
    ``getattr`` so a NullPool (tests) degrades to zeros instead of raising.
    """
    pool = engine.pool
    size_fn = getattr(pool, "size", None)
    checkedout_fn = getattr(pool, "checkedout", None)
    pool_size = size_fn() if callable(size_fn) else 0
    in_use = checkedout_fn() if callable(checkedout_fn) else 0
    return in_use, pool_size


async def get_health(session: AsyncSession) -> Health:
    db_ok = await repo.db_ping(session)
    in_use, pool_size = _pool_stats()  # reads the engine pool, not the DB

    if db_ok:
        spots = await repo.count_spots(session)
        users_row = await repo.user_aggregates(session)
        users = HealthUsers(
            total=users_row.total,
            active=users_row.active,
            new7d=users_row.new7d,
            deleted30d=users_row.deleted30d,
            kakao=users_row.kakao,
        )
    else:
        # DB is down — the health page exists precisely to show this. Skip the
        # DB-touching aggregates (they would raise → 500) and report zeros so the
        # endpoint degrades to db.ok=false instead of 500ing (A01 §2.3/§3).
        spots = 0
        users = HealthUsers(total=0, active=0, new7d=0, deleted30d=0, kakao=0)

    return Health(
        api=HealthApi(version=API_VERSION, uptimeSec=uptime_seconds(), p95Ms=None),
        db=HealthDb(ok=db_ok, poolInUse=in_use, poolSize=pool_size, spots=spots),
        # Tunnel health check deferred (A01 §2.3) → honest nulls.
        tunnel=HealthTunnel(ok=None, detail=None),
        users=users,
    )
