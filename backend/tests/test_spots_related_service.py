"""list_related_spots — KTO TarRlteTar "related places" (ADR-0005/0015).

Uses a duck-typed FakeKto (canned areaBasedList1 rows, counts calls) and the
in-memory FakeRedis fixture. Asserts base-name filtering, rank ordering,
name→contentId resolution, the Redis 1h cache short-circuit, and graceful
degradation when KTO is down.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import KtoApiUnavailable, ResourceNotFound
from app.modules.spots.services import list_related_spots


class FakeKto:
    def __init__(self, rows: list[dict[str, Any]], *, fail: bool = False) -> None:
        self._rows = rows
        self._fail = fail
        self.calls = 0

    async def call(self, service: Any, operation: str, **params: Any) -> list[dict[str, Any]]:
        self.calls += 1
        if self._fail:
            raise KtoApiUnavailable()
        return list(self._rows)


def _rel(base: str, name: str, rank: int, **extra: Any) -> dict[str, Any]:
    return {
        "tAtsNm": base,
        "rlteTatsNm": name,
        "rlteRank": str(rank),
        "rlteCtgryMclsNm": extra.get("cat", "관광지"),
        "rlteRegnNm": "강원특별자치도",
        "rlteSignguNm": "춘천시",
        "rlteBsicAdres": extra.get("addr", "강원특별자치도 춘천시 어딘가"),
    }


ROWS = [
    _rel("테스트관광지", "춘천향교", 1),
    _rel("테스트관광지", "카페감자밭", 2, cat="카페/찻집"),
    _rel("테스트관광지", "의암호", 3),
    _rel("다른관광지", "무관장소", 1),  # different base — must be filtered out
]


async def _seed_spot(
    session: AsyncSession, content_id: str, title: str, *, regn: str | None, signgu: str | None
) -> None:
    if signgu is not None:
        # FK: spots.ldong_signgu_cd → sigungus. The test DB seeds regions but
        # not sigungus, so ensure the row exists first.
        await session.execute(
            text(
                "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
                "VALUES (:s, :r, :nm) ON CONFLICT (ldong_signgu_cd) DO NOTHING"
            ),
            {"s": signgu, "r": regn, "nm": "춘천시"},
        )
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, show_flag, "
            "ldong_regn_cd, ldong_signgu_cd) VALUES (:cid, 12, :t, 1, :r, :s)"
        ),
        {"cid": content_id, "t": title, "r": regn, "s": signgu},
    )


@pytest.mark.asyncio
async def test_filters_by_base_resolves_ids_and_orders_by_rank(
    db_session: AsyncSession, redis_client_fake: Any
) -> None:
    await _seed_spot(db_session, "rel_q", "테스트관광지", regn="51", signgu="51110")
    await _seed_spot(db_session, "rel_hyang", "춘천향교", regn="51", signgu="51110")
    await _seed_spot(db_session, "rel_uam", "의암호", regn="51", signgu="51110")
    # 카페감자밭 / 무관장소 intentionally not in our spots

    kto = FakeKto(ROWS)
    rows = await list_related_spots(db_session, kto, redis_client_fake, "rel_q")

    names = [r.name for r in rows]
    assert names == ["춘천향교", "카페감자밭", "의암호"]  # base-filtered, rank-ordered
    by_name = {r.name: r for r in rows}
    assert by_name["춘천향교"].content_id == "rel_hyang"  # resolved → deep-linkable
    assert by_name["의암호"].content_id == "rel_uam"
    assert by_name["카페감자밭"].content_id is None  # not in our catalog → plain chip
    assert by_name["카페감자밭"].category == "카페/찻집"
    assert by_name["춘천향교"].address == "강원특별자치도 춘천시 어딘가"


@pytest.mark.asyncio
async def test_second_call_is_served_from_cache(
    db_session: AsyncSession, redis_client_fake: Any
) -> None:
    await _seed_spot(db_session, "rel_c", "테스트관광지", regn="51", signgu="51110")
    kto = FakeKto(ROWS)

    await list_related_spots(db_session, kto, redis_client_fake, "rel_c")
    calls_after_first = kto.calls
    assert calls_after_first >= 1

    again = await list_related_spots(db_session, kto, redis_client_fake, "rel_c")
    assert kto.calls == calls_after_first  # Redis hit — no further KTO calls
    assert [r.name for r in again] == ["춘천향교", "카페감자밭", "의암호"]


@pytest.mark.asyncio
async def test_kto_down_degrades_to_empty(db_session: AsyncSession, redis_client_fake: Any) -> None:
    await _seed_spot(db_session, "rel_d", "테스트관광지", regn="51", signgu="51110")
    rows = await list_related_spots(db_session, FakeKto([], fail=True), redis_client_fake, "rel_d")
    assert rows == []


@pytest.mark.asyncio
async def test_missing_region_codes_returns_empty_without_kto(
    db_session: AsyncSession, redis_client_fake: Any
) -> None:
    await _seed_spot(db_session, "rel_nogeo", "지역없음", regn=None, signgu=None)
    kto = FakeKto(ROWS)
    rows = await list_related_spots(db_session, kto, redis_client_fake, "rel_nogeo")
    assert rows == []
    assert kto.calls == 0  # no codes → never hits KTO


@pytest.mark.asyncio
async def test_unknown_spot_raises(db_session: AsyncSession, redis_client_fake: Any) -> None:
    with pytest.raises(ResourceNotFound):
        await list_related_spots(db_session, FakeKto(ROWS), redis_client_fake, "ghost")
