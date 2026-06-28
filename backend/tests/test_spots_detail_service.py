"""SPT load_spot_detail — lazy KTO fetch + 7-day cache + stale/partial fallback."""

from __future__ import annotations

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import KtoApiUnavailable, ResourceNotFound
from app.modules.spots.services import load_spot_detail


@pytest.fixture
def redis() -> FakeRedis:
    return FakeRedis(decode_responses=True)


class FakeKto:
    """Duck-typed KtoClient. Records call count; returns fixtures or raises."""

    def __init__(self, common=None, images=None, intro=None, *, fail: bool = False) -> None:
        self._common = common if common is not None else []
        self._images = images if images is not None else []
        self._intro = intro if intro is not None else []
        self.fail = fail
        self.calls = 0

    async def call(self, service, operation, **params):
        self.calls += 1
        if self.fail:
            raise KtoApiUnavailable()
        if operation == "detailCommon2":
            return self._common
        if operation == "detailImage2":
            return self._images
        if operation == "detailIntro2":
            return self._intro
        return []


async def _insert_spot(
    session: AsyncSession,
    content_id: str,
    *,
    show_flag: int = 1,
    region_cd: str | None = None,
    sigungu_cd: str | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "addr1, addr2, show_flag, ldong_regn_cd, ldong_signgu_cd) "
            "VALUES (:cid, 12, :t, 'http://kto/first.jpg', 'addr1', 'addr2', :sf, :rc, :sc)"
        ),
        {
            "cid": content_id,
            "t": f"title-{content_id}",
            "sf": show_flag,
            "rc": region_cd,
            "sc": sigungu_cd,
        },
    )


async def _insert_detail(
    session: AsyncSession,
    content_id: str,
    *,
    overview: str | None,
    age_days: int,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_details (content_id, content_type_id, overview, homepage, tel, cached_at) "
            "VALUES (:cid, 12, :ov, 'http://hp', '02-000', now() - (:age || ' days')::interval)"
        ),
        {"cid": content_id, "ov": overview, "age": str(age_days)},
    )


async def _insert_image(session: AsyncSession, content_id: str, sort_order: int, url: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_images (content_id, origin_image_url, small_image_url, sort_order) "
            "VALUES (:cid, :url, :small, :so)"
        ),
        {"cid": content_id, "url": url, "small": f"{url}/s", "so": sort_order},
    )


_COMMON = [{"overview": "한라산 정상 풍경", "homepage": "<a>hp</a>", "tel": "064-000"}]
_IMAGES = [
    {"originimgurl": "http://kto/1.jpg", "smallimageurl": "http://kto/1s.jpg", "serialnum": "1"},
    {"originimgurl": "http://kto/2.jpg", "smallimageurl": "http://kto/2s.jpg", "serialnum": "2"},
]
_INTRO = [{"usetime": "09:30~17:30", "restdate": "매주 월요일", "parking": "불가"}]


@pytest.mark.asyncio
async def test_404_unknown_spot(db_session: AsyncSession, redis: FakeRedis) -> None:
    with pytest.raises(ResourceNotFound):
        await load_spot_detail(db_session, FakeKto(), redis, "ghost-xyz")


@pytest.mark.asyncio
async def test_404_hidden_spot(db_session: AsyncSession, redis: FakeRedis) -> None:
    await _insert_spot(db_session, "DT-HID", show_flag=0)
    with pytest.raises(ResourceNotFound):
        await load_spot_detail(db_session, FakeKto(), redis, "DT-HID")


@pytest.mark.asyncio
async def test_fresh_cache_skips_kto(db_session: AsyncSession, redis: FakeRedis) -> None:
    await _insert_spot(db_session, "DT-FRESH")
    await _insert_detail(db_session, "DT-FRESH", overview="cached overview", age_days=1)
    await _insert_image(db_session, "DT-FRESH", 0, "http://cached/0.jpg")
    kto = FakeKto(_COMMON, _IMAGES)

    row = await load_spot_detail(db_session, kto, redis, "DT-FRESH")

    assert kto.calls == 0
    assert row.detail_status == "fresh"
    assert row.overview == "cached overview"
    assert [i.origin_image_url for i in row.images] == ["http://cached/0.jpg"]


@pytest.mark.asyncio
async def test_modified_time_supersedes_fresh_cache(
    db_session: AsyncSession, redis: FakeRedis
) -> None:
    """A detail within TTL is still refetched when spots.modified_time is newer
    than cached_at (pipeline signalled a KTO content change) (#37)."""
    await _insert_spot(db_session, "DT-MODIFIED")
    await _insert_detail(db_session, "DT-MODIFIED", overview="old", age_days=1)
    await db_session.execute(
        text("UPDATE spots SET modified_time = now() WHERE content_id = 'DT-MODIFIED'")
    )
    kto = FakeKto(_COMMON, _IMAGES)

    row = await load_spot_detail(db_session, kto, redis, "DT-MODIFIED")

    assert kto.calls == 3  # cache busted: refetched despite being within TTL
    assert row.detail_status == "fresh"
    assert row.overview == "한라산 정상 풍경"


@pytest.mark.asyncio
async def test_cache_miss_fetches_then_caches(db_session: AsyncSession, redis: FakeRedis) -> None:
    await _insert_spot(db_session, "DT-MISS")
    kto = FakeKto(_COMMON, _IMAGES)

    row = await load_spot_detail(db_session, kto, redis, "DT-MISS")
    assert kto.calls == 3  # common + image + intro
    assert row.detail_status == "fresh"
    assert row.overview == "한라산 정상 풍경"
    assert [i.origin_image_url for i in row.images] == ["http://kto/1.jpg", "http://kto/2.jpg"]

    kto2 = FakeKto(_COMMON, _IMAGES)
    row2 = await load_spot_detail(db_session, kto2, redis, "DT-MISS")
    assert kto2.calls == 0
    assert row2.overview == "한라산 정상 풍경"


@pytest.mark.asyncio
async def test_stale_cache_refetches(db_session: AsyncSession, redis: FakeRedis) -> None:
    await _insert_spot(db_session, "DT-STALE")
    await _insert_detail(db_session, "DT-STALE", overview="old", age_days=8)
    kto = FakeKto(_COMMON, _IMAGES)

    row = await load_spot_detail(db_session, kto, redis, "DT-STALE")
    assert kto.calls == 3
    assert row.detail_status == "fresh"
    assert row.overview == "한라산 정상 풍경"


@pytest.mark.asyncio
async def test_kto_failure_no_cache_is_unavailable(
    db_session: AsyncSession, redis: FakeRedis
) -> None:
    await _insert_spot(db_session, "DT-NOCACHE")
    kto = FakeKto(fail=True)

    row = await load_spot_detail(db_session, kto, redis, "DT-NOCACHE")
    assert row.detail_status == "unavailable"
    assert row.overview is None
    assert row.images == []
    assert row.title == "title-DT-NOCACHE"
    assert row.first_image_url == "http://kto/first.jpg"


@pytest.mark.asyncio
async def test_kto_failure_with_stale_serves_stale(
    db_session: AsyncSession, redis: FakeRedis
) -> None:
    await _insert_spot(db_session, "DT-STALEFAIL")
    await _insert_detail(db_session, "DT-STALEFAIL", overview="stale overview", age_days=10)
    await _insert_image(db_session, "DT-STALEFAIL", 0, "http://stale/0.jpg")
    kto = FakeKto(fail=True)

    row = await load_spot_detail(db_session, kto, redis, "DT-STALEFAIL")
    assert row.detail_status == "stale"
    assert row.overview == "stale overview"
    assert [i.origin_image_url for i in row.images] == ["http://stale/0.jpg"]


@pytest.mark.asyncio
async def test_region_sigungu_meta(db_session: AsyncSession, redis: FakeRedis) -> None:
    await db_session.execute(
        text(
            "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
            "VALUES ('11110', '11', '종로구') ON CONFLICT DO NOTHING"
        )
    )
    await _insert_spot(db_session, "DT-GEO", region_cd="11", sigungu_cd="11110")
    await _insert_detail(db_session, "DT-GEO", overview="x", age_days=1)

    row = await load_spot_detail(db_session, FakeKto(), redis, "DT-GEO")
    assert row.region_name is not None
    assert row.sigungu_name == "종로구"
    assert not hasattr(row, "moods")


@pytest.mark.asyncio
async def test_overview_stored_verbatim(db_session: AsyncSession, redis: FakeRedis) -> None:
    await _insert_spot(db_session, "DT-VERB")
    verbatim = "한라산\n  <b>정상</b>에서 본 풍경  "
    kto = FakeKto([{"overview": verbatim, "homepage": "", "tel": ""}], [])

    row = await load_spot_detail(db_session, kto, redis, "DT-VERB")
    assert row.overview == verbatim

    cached = await db_session.scalar(
        text("SELECT overview FROM spot_details WHERE content_id = 'DT-VERB'")
    )
    assert cached == verbatim


@pytest.mark.asyncio
async def test_image_replace_drops_trailing_no_duplicates(
    db_session: AsyncSession, redis: FakeRedis
) -> None:
    await _insert_spot(db_session, "DT-REPL")
    await _insert_detail(db_session, "DT-REPL", overview="x", age_days=8)
    await _insert_image(db_session, "DT-REPL", 0, "http://old/0.jpg")
    await _insert_image(db_session, "DT-REPL", 1, "http://old/1.jpg")
    await _insert_image(db_session, "DT-REPL", 2, "http://old/2.jpg")
    kto = FakeKto(_COMMON, [{"originimgurl": "http://new/0.jpg", "smallimageurl": None}])

    row = await load_spot_detail(db_session, kto, redis, "DT-REPL")
    assert [i.origin_image_url for i in row.images] == ["http://new/0.jpg"]

    count = await db_session.scalar(
        text("SELECT count(*) FROM spot_images WHERE content_id = 'DT-REPL'")
    )
    assert count == 1


@pytest.mark.asyncio
async def test_intro_persisted_and_returned(db_session: AsyncSession, redis: FakeRedis) -> None:
    await _insert_spot(db_session, "DT-INTRO")
    kto = FakeKto(_COMMON, _IMAGES, _INTRO)

    row = await load_spot_detail(db_session, kto, redis, "DT-INTRO")
    assert row.intro is not None
    assert row.intro.usetime == "09:30~17:30"
    assert row.intro.restdate == "매주 월요일"

    # second load serves from cache (intro_data persisted), no KTO calls
    kto2 = FakeKto(_COMMON, _IMAGES, _INTRO)
    row2 = await load_spot_detail(db_session, kto2, redis, "DT-INTRO")
    assert kto2.calls == 0
    assert row2.intro is not None
    assert row2.intro.usetime == "09:30~17:30"


@pytest.mark.asyncio
async def test_category_from_lcls3(db_session: AsyncSession, redis: FakeRedis) -> None:
    await db_session.execute(
        text(
            "INSERT INTO lcls_systm_codes "
            "(lcls_systm3_cd, lcls_systm2_cd, lcls_systm1_cd, "
            " lcls_systm3_nm, lcls_systm2_nm, lcls_systm1_nm) "
            "VALUES ('HS010100','HS01','HS','사적지','역사유적지','역사관광') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await _insert_spot(db_session, "DT-CAT")
    await db_session.execute(
        text("UPDATE spots SET lcls_systm3 = 'HS010100' WHERE content_id = 'DT-CAT'")
    )
    await _insert_detail(db_session, "DT-CAT", overview="x", age_days=1)

    row = await load_spot_detail(db_session, FakeKto(), redis, "DT-CAT")
    assert row.category == "사적지"
