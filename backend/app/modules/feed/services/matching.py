from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.db import async_session_factory
from app.core.logging import get_logger
from app.kto.display import T1_TILE_WIDTH, t1_display_url
from app.modules.feed import repositories
from app.modules.feed.text import first_sentence
from app.web.errors import ResourceNotFound

logger = get_logger(__name__)

MATCH_COUNT = 3


@dataclass(frozen=True)
class MatchRow:
    content_id: str
    title: str
    region_label: str
    image_url: str
    overview_first: str | None
    cpyrht_div_cd: str | None = None


def display_image_url(row: MatchRow) -> str:
    return t1_display_url(row.image_url, row.cpyrht_div_cd, width=T1_TILE_WIDTH) or row.image_url


def _to_match_row(row: repositories.MatchRow) -> MatchRow:
    return MatchRow(
        content_id=row.content_id,
        title=row.title,
        region_label=row.region_label,
        image_url=row.image_url,
        overview_first=first_sentence(row.overview),
        cpyrht_div_cd=row.cpyrht_div_cd,
    )


async def find_matches(session: AsyncSession, overseas_id: int) -> list[MatchRow]:
    if await repositories.get_overseas_brief(session, overseas_id) is None:
        raise ResourceNotFound(f"overseas spot {overseas_id} not found")
    grouped = await repositories.load_matches(session, [overseas_id])
    return [_to_match_row(row) for row in grouped.get(overseas_id, [])][:MATCH_COUNT]


async def load_matches_by_post(
    session: AsyncSession, overseas_ids: list[int]
) -> dict[int, list[MatchRow]]:
    grouped = await repositories.load_matches(session, overseas_ids)
    return {
        oid: [_to_match_row(row) for row in rows][:MATCH_COUNT] for oid, rows in grouped.items()
    }


async def precompute_matches(
    session: AsyncSession, *, limit: int | None = None, only_missing: bool = False
) -> dict[str, int]:
    """탐색 피드가 매칭을 인라인으로 받으려면 행마다 pgvector 검색을 돌 수 없다.

    실측(운영 덤프 2,573건): 전수 58초. only_missing 은 배포 훅용이다 — 첫 배포만
    전수를 물고, 이후 배포는 신규 Wikidata 행만 채운다.
    """
    targets = await repositories.collect_match_targets(session, only_missing=only_missing)
    if limit is not None:
        targets = targets[:limit]
    counters = {"targets": len(targets), "matched": 0, "empty": 0}
    for overseas_id in targets:
        neighbors = await repositories.find_domestic_neighbors(
            session, overseas_id, limit=settings.MATCH_CANDIDATES
        )
        ranked = [
            (content_id, distance)
            for content_id, _image_url, distance in neighbors
            if distance <= settings.MATCH_DISTANCE_MAX
        ][:MATCH_COUNT]
        await repositories.replace_matches(session, overseas_id, ranked)
        await session.commit()
        if ranked:
            counters["matched"] += 1
        else:
            counters["empty"] += 1
    logger.info("feed.match.precompute", **counters)
    return counters


async def recompute_all_matches() -> dict[str, int]:
    """임베딩이 바뀌면 매칭도 다시 계산해야 한다 — 임베딩 잡의 finally 에 붙는 훅.

    여기서 던지면 호출자의 잡 락 해제가 통째로 날아간다. 실패는 삼키고 다음
    pipeline-daily 실행에 맡긴다 — 정본 재계산은 scripts.precompute_matches 다.
    """
    try:
        async with async_session_factory() as session:
            return await precompute_matches(session)
    except Exception as exc:
        logger.warning("feed.match.recompute_failed", error=str(exc))
        return {"targets": 0, "matched": 0, "empty": 0}
