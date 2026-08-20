from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.services import retrieve
from app.modules.spots.services import MERGED_SIDOS, RegionPrefix

pytestmark = pytest.mark.asyncio


def test_a_merged_sido_yields_both_spellings() -> None:
    """코드 테이블은 전라남도, 주소는 전남광주통합특별시 — 한쪽만 쓰면 매칭이 0이다."""
    resolved = RegionPrefix(prefix="전라남도 여수시", sido="전라남도")

    assert resolved.prefixes == ["전라남도 여수시", "전남광주통합특별시 여수시"]


def test_an_unmerged_sido_yields_one_spelling() -> None:
    resolved = RegionPrefix(prefix="경상남도 통영시", sido="경상남도")

    assert resolved.prefixes == ["경상남도 통영시"]


def test_gwangju_merged_into_the_same_name() -> None:
    """광산구가 전남광주통합특별시 주소로 들어온다 — 광주도 같은 통합명을 쓴다."""
    assert MERGED_SIDOS["광주광역시"] == MERGED_SIDOS["전라남도"]


async def test_a_merged_region_hint_matches_the_address_actually_stored(
    db_session: AsyncSession,
) -> None:
    """운영 주소는 전남광주통합특별시로 오는데 코드 테이블은 전라남도다."""
    known = await db_session.scalar(text("SELECT 1 FROM sigungus WHERE ldong_signgu_nm = '여수시'"))
    if known is None:
        pytest.skip("지역 코드 테이블이 비어 있는 환경")

    prefixes = await retrieve.resolve_region_prefixes(db_session, hints=["여수"])

    assert "전남광주통합특별시 여수시" in prefixes
    assert "전라남도 여수시" in prefixes
