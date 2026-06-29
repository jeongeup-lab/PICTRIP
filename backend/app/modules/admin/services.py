"""admin services — read-only aggregation + health probes (A01 §2/§3).

Transaction-free (read-only). Calls :mod:`repositories`, shapes rows into the
§3 DTOs. No HTTP concerns (routes wrap the DTO in the JSend envelope).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import BackgroundTasks
from redis.asyncio import Redis
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.db import engine
from app.core.exceptions import (
    AdminCurationNotFound,
    AdminHistoryNotFound,
    AdminTriggerFailed,
    AdminValidationFailed,
)
from app.core.logging import get_logger
from app.core.version import API_VERSION, uptime_seconds
from app.modules.admin import repositories as repo
from app.modules.admin.schemas import (
    CollectionSource,
    CollectionStatus,
    CoverSpot,
    CurationDetail,
    CurationList,
    CurationListItem,
    CurationPreview,
    CurationUpdate,
    EmbeddingRecent,
    EmbeddingStatus,
    EmbeddingTriggerResult,
    Handpick,
    HandpickList,
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
    PreviewSpot,
    SpotSearchItem,
    SpotSearchResult,
    SpotsUpdate,
    TriggerResult,
)
from app.modules.admin.triggers import get_collection_trigger
from app.modules.images import services as image_services
from app.modules.spots.services.curations import (
    invalidate_curation_cache,
    load_curation,
    resolve_curation_spots,
)

_SOURCE_NAME = "국문 관광정보 서비스"
_SOURCE_ENDPOINT = "areaBasedSyncList2"

# Fixed admin actor (A04 single Basic user); no role/user table exists (out of scope).
_ADMIN_ACTOR = "admin"
_MAX_HANDPICKS = 8

# Re-embed trigger: a Redis lock doubles as the "running" flag for the status card
# and the concurrency guard for the button (SET NX). TTL auto-releases a crashed
# job. The "missing" (full-backlog) scope is capped so a background run never pins
# the serving process — larger backlogs go through scripts.backfill_embeddings.
_EMBED_LOCK_KEY = "admin:embed:running"
_EMBED_LOCK_TTL = 1800  # seconds (30 min)
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
        embeddedSpots=embedded,
        source=CollectionSource(
            name=_SOURCE_NAME,
            endpoint=_SOURCE_ENDPOINT,
            lastRun=last_run,
        ),
        # Honest null: no scheduler metadata is wired yet (A01 §2.1 allows it).
        nextScheduledAt=None,
    )


# --- embedding status + re-embed trigger (collection/embedding are separate) ---
async def get_embedding_status(session: AsyncSession, redis: Redis) -> EmbeddingStatus:
    """Coverage + failure backlog + "this collection" progress (A01-extension).

    Embedding runs after collection: a spot can have ``first_image_url`` but no
    ``spot_embeddings`` row. ``embedding_failures`` makes "failed" distinguishable
    from "not yet attempted". The "recent" view scopes to the latest sync run's
    start so the operator sees whether today's newly-collected spots are embedded.
    """
    totals = await repo.embedding_totals(session)
    reasons = {r.reason: r.n for r in await repo.embedding_failures_by_reason(session)}

    with_image = totals.with_image
    missing = totals.missing
    embedded = with_image - missing
    failed = totals.failed

    # Scope "this collection" to the latest sync run's start. sync_runs is
    # pipeline-owned and always present in prod; guard defensively so a DB that
    # has never been synced degrades to a null window instead of 500ing.
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

    running = bool(await redis.exists(_EMBED_LOCK_KEY))

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
    task releases it on completion. The write itself goes through
    :mod:`app.modules.images.services` (cross-module via services, never models).
    """
    if scope not in ("failed", "missing"):
        raise AdminValidationFailed(
            details=[{"field": "scope", "issue": "scope는 failed 또는 missing이어야 합니다."}]
        )

    acquired = await redis.set(_EMBED_LOCK_KEY, actor, nx=True, ex=_EMBED_LOCK_TTL)
    if not acquired:
        _audit_embed(actor, accepted=False, scope=scope, reason="already-running")
        raise AdminTriggerFailed("이미 임베딩이 진행 중입니다.")

    only_failed = scope == "failed"
    limit = None if only_failed else _EMBED_TRIGGER_MAX
    background_tasks.add_task(_run_embed_job, redis, only_failed, limit)
    _audit_embed(actor, accepted=True, scope=scope, reason=None)
    return EmbeddingTriggerResult(job=f"embed-{scope}", scope=scope, accepted=True)


async def _run_embed_job(redis: Redis, only_failed: bool, limit: int | None) -> None:
    """Background worker: run the embed job, always releasing the Redis lock."""
    try:
        await image_services.run_embedding_job(only_failed=only_failed, limit=limit)
    except Exception:  # never let a background failure leave the lock dangling
        _logger.exception("embed.job.error")
    finally:
        await redis.delete(_EMBED_LOCK_KEY)


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


# --- collection trigger (A01 §3/§5 Phase 2 / ADM-009·010) ---------------------
async def trigger_collection(
    session: AsyncSession,
    actor: str = _ADMIN_ACTOR,
) -> TriggerResult:
    """Kick the daily collection (``sync-daily``) via the A7 trigger adapter.

    Read-only on our DB: the actual write (``sync_runs``) happens in the
    pipeline run the trigger kicks. No transaction boundary here.

    CONCURRENCY (my decision; A7 left it open): if the latest sync_run is still
    ``running`` we REJECT (the button must not double-fire) before touching the
    adapter, so a stuck/in-flight run can't be stampeded.
    """
    latest = await repo.latest_sync_run(session)
    # App-level guard — best-effort. There is a TOCTOU window between this read
    # and the workflow_dispatch below (two requests can race through). The
    # AUTHORITATIVE guard against double-runs is the GitHub Actions
    # ``concurrency.group: pipeline-sync`` in
    # ``.github/workflows/pipeline-sync.yml`` — that serialises at the CI layer.
    if latest is not None and latest.status == "running":
        _audit_trigger(actor, accepted=False, ref=None, reason="already-running")
        raise AdminTriggerFailed("이미 수집이 진행 중입니다.")

    try:
        ref = await get_collection_trigger().trigger("sync-daily")
    except AdminTriggerFailed:
        # Distinguish the two failure modes in the audit so operators can tell
        # a misconfiguration from a live GitHub error without reading the message.
        # Token check mirrors WorkflowDispatchTrigger.trigger() — no token value logged.
        audit_reason = "not-configured" if not settings.GITHUB_DISPATCH_TOKEN else "github-error"
        _audit_trigger(actor, accepted=False, ref=None, reason=audit_reason)
        raise

    _audit_trigger(actor, accepted=True, ref=ref, reason=None)
    return TriggerResult(job="sync-daily", runId=ref, accepted=True)


def _audit_trigger(actor: str, *, accepted: bool, ref: str | None, reason: str | None) -> None:
    # ADM-010 audit: one structured log line per trigger call via app.core.logging
    # (same JSON pipeline as the curation-write audit below). No audit table —
    # the structured line is the record (actor · action · job · result · ref).
    _logger.info(
        "collection.trigger",
        actor=actor,
        action="collection.trigger",
        job="sync-daily",
        result="accepted" if accepted else "failed",
        ref=ref,
        reason=reason,
    )


# --- curation editor (A01 §7 / ADM-012~016) -----------------------------------
# This is the admin module's only write surface; transaction commit boundaries
# live here (repos mutate the passed session, services commit). Every write
# invalidates the on-publish cache and emits a structured audit line.


async def list_curations(session: AsyncSession) -> CurationList:
    rows = await repo.list_curations(session)
    by_type: dict[str, list[CurationListItem]] = {"region": [], "mood": [], "editorial": []}
    for r in rows:
        item = CurationListItem(
            id=r.id,
            type=r.type,
            slug=r.slug,
            title=r.title,
            subtitle=r.subtitle,
            coverUrl=r.cover_url,
            isPublished=r.is_published,
            position=r.position,
        )
        by_type.setdefault(r.type, []).append(item)
    # rows arrive ordered by (type, position); the per-group lists preserve it.
    return CurationList(
        heroes=by_type["region"],
        rails=by_type["mood"],
        editorial=by_type["editorial"],
    )


async def _build_detail(session: AsyncSession, curation) -> CurationDetail:  # type: ignore[no-untyped-def]
    cover: CoverSpot | None = None
    if curation.cover_spot_id is not None:
        row = await repo.get_cover_spot(session, curation.cover_spot_id)
        if row is not None:
            cover = CoverSpot(
                contentId=row.content_id, name=row.title, imageUrl=row.first_image_url
            )
    hp_rows = await repo.curation_handpicks(session, curation.id)
    handpicks = [
        Handpick(
            contentId=h.content_id,
            name=h.title,
            category=h.category,
            imageUrl=h.first_image_url,
            position=h.position,
        )
        for h in hp_rows
    ]
    return CurationDetail(
        id=curation.id,
        type=curation.type,
        slug=curation.slug,
        title=curation.title,
        subtitle=curation.subtitle,
        lead=curation.lead,
        intro=curation.intro,
        coverSpot=cover,
        regionCd=curation.region_cd,
        moodId=curation.mood_id,
        isPublished=curation.is_published,
        position=curation.position,
        handpicks=handpicks,
    )


async def get_curation_detail(session: AsyncSession, curation_id: int) -> CurationDetail:
    curation = await repo.get_curation(session, curation_id)
    if curation is None:
        raise AdminCurationNotFound
    return await _build_detail(session, curation)


async def get_curation_preview(
    session: AsyncSession, redis: Redis, curation_id: int
) -> CurationPreview:
    """Resolved display spots (handpicked, else the quality-gate auto-fill pool).

    Reuses the live feed resolver so the editor preview matches what the app
    actually renders — crucially, it surfaces the auto-filled spots for curations
    with no handpicks instead of a placeholder.
    """
    try:
        row = await load_curation(session, curation_id)
    except NoResultFound as exc:
        raise AdminCurationNotFound from exc
    spots = await resolve_curation_spots(session, redis, row)
    return CurationPreview(
        spots=[
            PreviewSpot(
                contentId=s.content_id,
                name=s.title,
                category=s.lcls_systm3_nm or s.category,
                imageUrl=s.first_image_url,
            )
            for s in spots
        ]
    )


async def update_curation(
    session: AsyncSession,
    redis: Redis,
    curation_id: int,
    body: CurationUpdate,
) -> CurationDetail:
    curation = await repo.get_curation(session, curation_id)
    if curation is None:
        raise AdminCurationNotFound

    details: list[dict[str, str]] = []
    title = body.title  # newlines allowed; only reject blank-after-strip
    if not title.strip():
        details.append({"field": "title", "issue": "제목은 비워둘 수 없습니다."})
    if body.position < 0:
        details.append({"field": "position", "issue": "노출 순서는 0 이상이어야 합니다."})
    if body.coverSpotId is not None and not await repo.spot_exposable_with_image(
        session, body.coverSpotId
    ):
        # 표지 스팟은 존재 + 노출(show_flag=1) + 대표 이미지가 모두 있어야 함 (A01 §7).
        details.append(
            {
                "field": "coverSpotId",
                "issue": "표지 스팟이 없거나 노출 불가하거나 이미지가 없습니다.",
            }
        )
    if details:
        raise AdminValidationFailed(details=details)

    await repo.update_curation_fields(
        session,
        curation,
        title=title,
        subtitle=body.subtitle,
        lead=body.lead,
        intro=body.intro,
        cover_spot_id=body.coverSpotId,
        is_published=body.isPublished,
        position=body.position,
    )
    # Defensive: type/scope are not editable here, so ck_curation_scope still
    # holds; the COMMIT would surface any DB-level CHECK violation regardless.
    await session.commit()
    await invalidate_curation_cache(redis, curation_id)  # ADM-016 on-publish DEL
    _audit("curation.update", curation)
    return await _build_detail(session, curation)


async def set_curation_spots(
    session: AsyncSession,
    redis: Redis,
    curation_id: int,
    body: SpotsUpdate,
) -> HandpickList:
    curation = await repo.get_curation(session, curation_id)
    if curation is None:
        raise AdminCurationNotFound

    spot_ids = body.spotIds
    details: list[dict[str, str]] = []
    if len(spot_ids) > _MAX_HANDPICKS:
        details.append(
            {"field": "spotIds", "issue": f"손픽 스팟은 최대 {_MAX_HANDPICKS}개까지 가능합니다."}
        )
    if len(set(spot_ids)) != len(spot_ids):
        details.append({"field": "spotIds", "issue": "중복된 스팟이 있습니다."})
    if spot_ids:
        existing = await repo.existing_spot_ids(session, spot_ids)
        missing = [cid for cid in spot_ids if cid not in existing]
        if missing:
            details.append(
                {"field": "spotIds", "issue": f"존재하지 않는 스팟: {', '.join(missing)}"}
            )
    if details:
        raise AdminValidationFailed(details=details)

    await repo.replace_curation_spots(session, curation_id, spot_ids)
    curation.updated_at = datetime.now(tz=UTC)
    await session.commit()
    await invalidate_curation_cache(redis, curation_id)  # ADM-016 on-publish DEL
    _audit("curation.spots", curation, count=len(spot_ids))

    hp_rows = await repo.curation_handpicks(session, curation_id)
    return HandpickList(
        handpicks=[
            Handpick(
                contentId=h.content_id,
                name=h.title,
                category=h.category,
                imageUrl=h.first_image_url,
                position=h.position,
            )
            for h in hp_rows
        ]
    )


async def search_spots(
    session: AsyncSession, q: str, region: str | None, limit: int
) -> SpotSearchResult:
    rows = await repo.admin_spot_search(session, q, region, limit)
    return SpotSearchResult(
        spots=[
            SpotSearchItem(
                contentId=r.content_id,
                name=r.title,
                regionCd=r.ldong_regn_cd,
                regionName=r.region_name,
                imageUrl=r.first_image_url,
            )
            for r in rows
        ]
    )


def _audit(action: str, curation, **extra) -> None:  # type: ignore[no-untyped-def]
    # ADM-016 audit: no audit table exists (creating one is scope creep). Emit a
    # single structured log line per write via the app logger instead — actor +
    # action + what changed. Ingested by the same JSON log pipeline (app.core.logging).
    _logger.info(
        action,
        actor=_ADMIN_ACTOR,
        curationId=curation.id,
        slug=curation.slug,
        isPublished=curation.is_published,
        **extra,
    )
