from __future__ import annotations

import asyncio

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import async_session_factory
from app.core.logging import get_logger
from app.ml.embedding import embedder

logger = get_logger(__name__)

_embed_lock = asyncio.Lock()

_USER_AGENT = "PicTrip/1.0 (https://pictrip.org)"

_RETRY_STATUSES = frozenset({429, 503})
_MAX_DOWNLOAD_ATTEMPTS = 6
_MAX_BACKOFF_SECONDS = 120.0

_TARGETS_SQL = "SELECT id, image_url FROM overseas_spots WHERE embedding IS NULL ORDER BY id"
_WRITE_SQL = text(
    "UPDATE overseas_spots SET embedding = CAST(:emb AS halfvec(512)), "
    "updated_at = now() WHERE id = :oid AND image_url = :image_url RETURNING id"
)


async def collect_overseas_targets(
    session: AsyncSession, *, limit: int | None = None
) -> list[tuple[int, str]]:
    sql, params = _TARGETS_SQL, {}
    if limit:
        sql += " LIMIT :limit"
        params = {"limit": limit}
    rows = (await session.execute(text(sql), params)).all()
    return [(int(oid), url) for oid, url in rows]


def _retry_wait(resp: httpx.Response, attempt: int, backoff_base: float) -> float:
    retry_after = resp.headers.get("Retry-After")
    try:
        wait = float(retry_after) if retry_after is not None else backoff_base * (2**attempt)
    except ValueError:
        wait = backoff_base * (2**attempt)
    return min(wait, _MAX_BACKOFF_SECONDS)


async def _download(
    image_url: str,
    client: httpx.AsyncClient,
    dl_sem: asyncio.Semaphore,
    download_pace: float,
    backoff_base: float,
) -> httpx.Response:
    async with dl_sem:
        resp = await client.get(image_url, timeout=20.0, follow_redirects=True)
        for attempt in range(_MAX_DOWNLOAD_ATTEMPTS - 1):
            if resp.status_code not in _RETRY_STATUSES:
                break
            await asyncio.sleep(_retry_wait(resp, attempt, backoff_base))
            resp = await client.get(image_url, timeout=20.0, follow_redirects=True)
        if download_pace:
            await asyncio.sleep(download_pace)
        return resp


async def _embed_one(
    oid: int,
    image_url: str,
    client: httpx.AsyncClient,
    dl_sem: asyncio.Semaphore,
    download_pace: float,
    backoff_base: float,
) -> tuple[int, str, list[float] | None]:
    try:
        resp = await _download(image_url, client, dl_sem, download_pace, backoff_base)
        if resp.status_code != 200 or not resp.content:
            logger.warning(
                "overseas.embed.download_failed", overseas_id=oid, status=resp.status_code
            )
            return (oid, image_url, None)
        async with _embed_lock:
            vector = await asyncio.to_thread(embedder.embed_image, resp.content)
        return (oid, image_url, vector)
    except Exception as exc:
        logger.warning("overseas.embed.failed", overseas_id=oid, error=str(exc))
        return (oid, image_url, None)


async def run_overseas_embedding_job(
    *,
    limit: int | None = None,
    concurrency: int = 2,
    batch_size: int = 50,
    download_pace: float = 0.3,
    backoff_base: float = 2.0,
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
) -> dict[str, int]:
    async with session_factory() as session:
        targets = await collect_overseas_targets(session, limit=limit)
    counters = {"targets": len(targets), "embedded": 0, "failed": 0, "skipped": 0}
    logger.info("overseas.embed.start", targets=len(targets))
    if not targets:
        return counters

    dl_sem = asyncio.Semaphore(max(1, concurrency))
    async with httpx.AsyncClient(headers={"User-Agent": _USER_AGENT}) as client:
        for i in range(0, len(targets), max(1, batch_size)):
            batch = targets[i : i + max(1, batch_size)]
            outcomes = await asyncio.gather(
                *(
                    _embed_one(oid, url, client, dl_sem, download_pace, backoff_base)
                    for oid, url in batch
                )
            )
            async with session_factory() as session:
                for oid, image_url, vector in outcomes:
                    if vector is None:
                        counters["failed"] += 1
                        continue
                    literal = "[" + ",".join(f"{v:.8f}" for v in vector) + "]"
                    written_id = (
                        await session.execute(
                            _WRITE_SQL,
                            {"emb": literal, "oid": oid, "image_url": image_url},
                        )
                    ).scalar_one_or_none()
                    if written_id is None:
                        counters["skipped"] += 1
                    else:
                        counters["embedded"] += 1
                await session.commit()
    logger.info(
        "overseas.embed.done",
        targets=counters["targets"],
        embedded=counters["embedded"],
        failed=counters["failed"],
        skipped=counters["skipped"],
    )
    return counters
