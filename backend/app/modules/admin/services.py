"""admin services — read-only aggregation + health probes (A01 §2/§3).

Transaction-free (read-only). Calls :mod:`repositories`, shapes rows into the
§3 DTOs. No HTTP concerns (routes wrap the DTO in the JSend envelope).
"""

from __future__ import annotations

from datetime import date

from fastapi import BackgroundTasks
from redis.asyncio import Redis
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.db import engine
from app.core.exceptions import (
    AdminHistoryNotFound,
    AdminOverseasNotFound,
    AdminTriggerFailed,
    AdminValidationFailed,
)
from app.core.logging import get_logger
from app.core.version import API_VERSION, uptime_seconds
from app.modules.admin import repositories as repo
from app.modules.admin.schemas import (
    CollectionSource,
    CollectionStatus,
    EmbeddingRecent,
    EmbeddingStatus,
    EmbeddingTriggerResult,
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
    OverseasList,
    OverseasListItem,
    OverseasVisibility,
    TriggerResult,
)
from app.modules.admin.triggers import get_collection_trigger
from app.modules.feed.services import invalidate_all_match_cache, invalidate_match_cache
from app.modules.images import services as image_services

_SOURCE_NAME = "국문 관광정보 서비스"
_SOURCE_ENDPOINT = "areaBasedSyncList2"

_ADMIN_ACTOR = "admin"

_EMBED_TRIGGER_MAX = 2000

_logger = get_logger(__name__)


async def get_collection_status(session: AsyncSession) -> CollectionStatus:
    total = await repo.count_spots(session)
    embedded = await repo.count_embeddings(session)
    row = await repo.latest_sync_run(session)

    last_run: LastRun | None = None
    if row is not None:
        last_run = LastRun(
            status=row.status,
            finishedAt=row.finished_at,
            ranAt=row.finished_at or row.started_at,
            apiCalls=row.api_calls,
            inserted=row.inserted,
            updated=row.updated,
            softDeleted=row.soft_deleted,
            durationSec=row.duration_sec,
        )

    return CollectionStatus(
        totalSpots=total,
        embeddedSpots=embedded,
        source=CollectionSource(
            name=_SOURCE_NAME,
            endpoint=_SOURCE_ENDPOINT,
            lastRun=last_run,
        ),
        nextScheduledAt=None,
    )


async def get_embedding_status(session: AsyncSession, redis: Redis) -> EmbeddingStatus:
    """Coverage + failure backlog + "this collection" progress (A01-extension).

    Embedding runs after collection: a spot can have ``first_image_url`` but no
    ``spot_embeddings`` row. ``embedding_failures`` makes "failed" distinguishable
    from "not yet attempted". The "recent" view scopes to the latest sync run's
    start so the operator sees whether today's newly-collected spots are embedded.
    ``sync_runs`` is pipeline-owned and always present in prod; the read is
    guarded defensively so a DB that has never been synced degrades to a null
    window instead of 500ing.
    """
    totals = await repo.embedding_totals(session)
    reasons = {r.reason: r.n for r in await repo.embedding_failures_by_reason(session)}

    with_image = totals.with_image
    missing = totals.missing
    embedded = with_image - missing
    failed = totals.failed

    since = None
    recent_target = recent_embedded = 0
    try:
        run = await repo.latest_sync_run(session)
        if run is not None:
            since = run.started_at
            window = await repo.embedding_recent_window(session, since)
            recent_target = window.target
            recent_embedded = window.embedded
    except SQLAlchemyError:
        await session.rollback()
        since = None

    running = bool(await redis.exists(image_services.EMBEDDING_JOB_LOCK_NAME))

    return EmbeddingStatus(
        totalSpots=totals.total_spots,
        withImage=with_image,
        embedded=embedded,
        missing=missing,
        failed=failed,
        pending=max(0, missing - failed),
        failuresByReason=reasons,
        recent=EmbeddingRecent(
            since=since,
            target=recent_target,
            embedded=recent_embedded,
            outstanding=max(0, recent_target - recent_embedded),
        ),
        lastComputedAt=totals.last_computed_at,
        running=running,
    )


async def trigger_embedding(
    redis: Redis,
    background_tasks: BackgroundTasks,
    scope: str = "failed",
    actor: str = _ADMIN_ACTOR,
) -> EmbeddingTriggerResult:
    """Kick an in-process re-embed job (A01-extension; admin-owned action).

    ``scope='failed'`` retries only spots in ``embedding_failures``; ``'missing'``
    processes the (capped) all-time backlog. A Redis ``SET NX`` lock rejects a
    second concurrent trigger and marks the status card "running"; the background
    task releases it on completion and the lock TTL auto-releases a crashed job.
    The "missing" scope is capped (``_EMBED_TRIGGER_MAX``) so a background run
    never pins the serving process — larger backlogs go through
    ``scripts.backfill_embeddings``. The write itself goes through
    :mod:`app.modules.images.services` (cross-module via services, never models).
    """
    if scope not in ("failed", "missing"):
        raise AdminValidationFailed(
            details=[{"field": "scope", "issue": "scope는 failed 또는 missing이어야 합니다."}]
        )

    lock = await image_services.acquire_embedding_job_lock(redis)
    if lock is None:
        _audit_embed(actor, accepted=False, scope=scope, reason="already-running")
        raise AdminTriggerFailed("이미 임베딩이 진행 중입니다.")

    only_failed = scope == "failed"
    limit = None if only_failed else _EMBED_TRIGGER_MAX
    background_tasks.add_task(_run_embed_job, redis, only_failed, limit, lock)
    _audit_embed(actor, accepted=True, scope=scope, reason=None)
    return EmbeddingTriggerResult(job=f"embed-{scope}", scope=scope, accepted=True)


async def _run_embed_job(
    redis: Redis,
    only_failed: bool,
    limit: int | None,
    lock: image_services.EmbeddingJobLock,
) -> None:
    """Background worker: run the embed job, always releasing the Redis lock."""
    try:
        await invalidate_all_match_cache(redis)
        await image_services.run_embedding_job(only_failed=only_failed, limit=limit)
    except Exception:
        _logger.exception("embed.job.error")
    finally:
        await invalidate_all_match_cache(redis)
        try:
            await image_services.release_embedding_job_lock(lock)
        except Exception as exc:
            _logger.warning("embed.lock.release_failed", error=str(exc))


def _audit_embed(actor: str, *, accepted: bool, scope: str, reason: str | None) -> None:
    _logger.info(
        "embedding.trigger",
        actor=actor,
        action="embedding.trigger",
        scope=scope,
        result="accepted" if accepted else "failed",
        reason=reason,
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
    """Component health card. When the DB is down — the page exists precisely to
    show this — the DB-touching aggregates are skipped and reported as zeros so
    the endpoint degrades to ``db.ok=false`` instead of 500ing. Pool stats read
    the live engine pool, not the DB."""
    db_ok = await repo.db_ping(session)
    in_use, pool_size = _pool_stats()

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
        spots = 0
        users = HealthUsers(total=0, active=0, new7d=0, deleted30d=0, kakao=0)

    return Health(
        api=HealthApi(version=API_VERSION, uptimeSec=uptime_seconds(), p95Ms=None),
        db=HealthDb(ok=db_ok, poolInUse=in_use, poolSize=pool_size, spots=spots),
        tunnel=HealthTunnel(ok=None, detail=None),
        users=users,
    )


async def trigger_collection(
    session: AsyncSession,
    actor: str = _ADMIN_ACTOR,
) -> TriggerResult:
    """Kick the daily collection (``sync-daily``) via the A7 trigger adapter.

    Read-only on our DB: the actual write (``sync_runs``) happens in the
    pipeline run the trigger kicks. No transaction boundary here.

    CONCURRENCY (my decision; A7 left it open): if the latest sync_run is still
    ``running`` we REJECT (the button must not double-fire) before touching the
    adapter, so a stuck/in-flight run can't be stampeded. This app-level guard is
    best-effort — there is a TOCTOU window between the read and the
    workflow_dispatch. The AUTHORITATIVE guard against double-runs is the GitHub
    Actions ``concurrency.group: pipeline-sync`` in
    ``.github/workflows/pipeline-sync.yml``, which serialises at the CI layer.
    """
    latest = await repo.latest_sync_run(session)
    if latest is not None and latest.status == "running":
        _audit_trigger(actor, accepted=False, ref=None, reason="already-running")
        raise AdminTriggerFailed("이미 수집이 진행 중입니다.")

    try:
        ref = await get_collection_trigger().trigger("sync-daily")
    except AdminTriggerFailed:
        audit_reason = "not-configured" if not settings.GITHUB_DISPATCH_TOKEN else "github-error"
        _audit_trigger(actor, accepted=False, ref=None, reason=audit_reason)
        raise

    _audit_trigger(actor, accepted=True, ref=ref, reason=None)
    return TriggerResult(job="sync-daily", runId=ref, accepted=True)


def _audit_trigger(actor: str, *, accepted: bool, ref: str | None, reason: str | None) -> None:
    """ADM-010 audit: one structured log line per trigger call — no audit table,
    the line is the record (actor · action · job · result · ref). ``reason``
    distinguishes a misconfiguration (not-configured) from a live GitHub error
    so operators can tell without reading the message; the token value is never
    logged."""
    _logger.info(
        "collection.trigger",
        actor=actor,
        action="collection.trigger",
        job="sync-daily",
        result="accepted" if accepted else "failed",
        ref=ref,
        reason=reason,
    )


async def list_overseas(
    session: AsyncSession, *, q: str | None, cursor_id: int | None, limit: int
) -> OverseasList:
    """One id-cursor page. Fetches limit+1 to know whether more rows follow;
    ``nextCursor`` is the last returned id when they do, else None."""
    q_norm = q.strip() if q else None
    rows = await repo.list_overseas(session, q=q_norm or None, cursor_id=cursor_id, limit=limit + 1)
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = page[-1].id if has_more and page else None
    return OverseasList(
        items=[
            OverseasListItem(
                id=r.id,
                nameKo=r.name_ko,
                countryNameKo=r.country_name_ko,
                imageUrl=r.image_url,
                fameScore=r.fame_score,
                isHidden=r.is_hidden,
            )
            for r in page
        ],
        nextCursor=next_cursor,
    )


async def set_overseas_visibility(
    session: AsyncSession,
    redis: Redis,
    overseas_id: int,
    hidden: bool,
    actor: str = _ADMIN_ACTOR,
) -> OverseasVisibility:
    """admin's scoped-write surface: only ``overseas_spots.is_hidden`` is written
    (CLAUDE.md grant). Hiding a spot is exactly the filter ``/v1/feed`` applies,
    so the toggle removes it from the app feed. One structured audit line per
    toggle."""
    found = await repo.set_overseas_hidden(session, overseas_id, hidden)
    if not found:
        raise AdminOverseasNotFound
    await session.commit()
    await invalidate_match_cache(redis, overseas_id)
    _logger.info(
        "overseas.visibility",
        actor=actor,
        overseasId=overseas_id,
        isHidden=hidden,
    )
    return OverseasVisibility(id=overseas_id, isHidden=hidden)
