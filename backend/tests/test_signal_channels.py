from __future__ import annotations

from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.feed.services.signal_channels import load_signal_channel_cached


async def _seed_region(session: AsyncSession, cd: str, name: str) -> None:
    await session.execute(
        text(
            "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES (:c, :n) "
            "ON CONFLICT DO NOTHING"
        ),
        {"c": cd, "n": name},
    )


async def _seed_spot(
    session: AsyncSession,
    cid: str,
    *,
    title: str,
    region: str = "26",
    lcls1: str = "NA",
    lcls2: str | None = None,
    photo_type: str = "view",
    aesthetic: float = 0.1,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, ldong_regn_cd, lcls_systm1, lcls_systm2) "
            "VALUES (:cid, 12, :t, 'http://kto/i.jpg', 1, :r, :l1, :l2)"
        ),
        {"cid": cid, "t": title, "r": region, "l1": lcls1, "l2": lcls2},
    )
    await session.execute(
        text(
            "INSERT INTO spot_visual (content_id, photo_type, aesthetic_score) "
            "VALUES (:cid, :pt, :sc)"
        ),
        {"cid": cid, "pt": photo_type, "sc": aesthetic},
    )


async def _seed_buzz(
    session: AsyncSession,
    cid: str,
    *,
    scope: str,
    mentions: int = 0,
    recent: float = 0.0,
    blog_total: int | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_buzz "
            "(content_id, scope, mentions, distinct_blogs, recent_ratio, blog_total) "
            "VALUES (:cid, :scope, :m, :m, :r, :t)"
        ),
        {"cid": cid, "scope": scope, "m": mentions, "r": recent, "t": blog_total},
    )


async def test_spot_channel_requires_photo_quality_and_buzz(db_session) -> None:
    await _seed_region(db_session, "26", "부산광역시")
    await _seed_spot(db_session, "good", title="뜨는 곳", aesthetic=0.1)
    await _seed_buzz(db_session, "good", scope="base", recent=1.0, blog_total=5000)
    await _seed_spot(db_session, "ugly", title="사진 나쁜 곳", aesthetic=-0.1)
    await _seed_buzz(db_session, "ugly", scope="base", recent=1.0, blog_total=9000)
    await _seed_spot(db_session, "silent", title="버즈 없는 곳", aesthetic=0.2)

    cards = await load_signal_channel_cached(db_session, FakeRedis(), "spot")

    assert [c.content_id for c in cards] == ["good"]
    assert cards[0].tag == "요즘뜨는"
    assert cards[0].rank == 1


async def test_spot_channel_spreads_across_regions(db_session) -> None:
    await _seed_region(db_session, "26", "부산광역시")
    await _seed_region(db_session, "50", "제주특별자치도")
    await _seed_spot(db_session, "b1", title="부산 1위", region="26", aesthetic=0.3)
    await _seed_buzz(db_session, "b1", scope="base", recent=1.0, blog_total=9000)
    await _seed_spot(db_session, "b2", title="부산 2위", region="26", aesthetic=0.2)
    await _seed_buzz(db_session, "b2", scope="base", recent=1.0, blog_total=8000)
    await _seed_spot(db_session, "j1", title="제주 1위", region="50", aesthetic=0.05)
    await _seed_buzz(db_session, "j1", scope="base", recent=0.9, blog_total=700)

    cards = await load_signal_channel_cached(db_session, FakeRedis(), "spot")

    assert {c.content_id for c in cards} == {"b1", "j1"}


async def test_cafe_channel_fences_to_cafes_and_tags_views(db_session) -> None:
    await _seed_region(db_session, "26", "부산광역시")
    await _seed_spot(
        db_session,
        "cafe1",
        title="뷰 카페",
        lcls1="FD",
        lcls2="FD05",
        photo_type="view",
        aesthetic=0.15,
    )
    await _seed_buzz(db_session, "cafe1", scope="부산:cafe", mentions=5, recent=1.0)
    await _seed_spot(db_session, "mountain", title="산", lcls1="NA", aesthetic=0.5)
    await _seed_buzz(db_session, "mountain", scope="base", recent=1.0, blog_total=90000)

    cards = await load_signal_channel_cached(db_session, FakeRedis(), "cafe")

    assert [c.content_id for c in cards] == ["cafe1"]
    assert cards[0].tag == "뷰맛집"


async def test_hidden_channel_wants_recent_talk_without_crowds(db_session) -> None:
    await _seed_region(db_session, "26", "부산광역시")
    await _seed_region(db_session, "50", "제주특별자치도")
    await _seed_spot(db_session, "quiet", title="숨은 계곡", region="50", aesthetic=0.1)
    await _seed_buzz(db_session, "quiet", scope="base", recent=0.9, blog_total=3000)
    await _seed_spot(db_session, "crowded", title="붐비는 명소", region="26", aesthetic=0.3)
    await _seed_buzz(db_session, "crowded", scope="base", recent=1.0, blog_total=5000)
    await db_session.execute(
        text(
            "INSERT INTO spot_concentration "
            "(content_id, concentration_rate, base_ymd, raw_name) "
            "VALUES ('crowded', 85.0, DATE '2026-08-01', '붐비는 명소')"
        )
    )
    await _seed_spot(db_session, "famous", title="이미 유명한 곳", region="26", aesthetic=0.2)
    await _seed_buzz(db_session, "famous", scope="base", recent=1.0, blog_total=500000)

    cards = await load_signal_channel_cached(db_session, FakeRedis(), "hidden")

    assert [c.content_id for c in cards] == ["quiet"]
    assert cards[0].tag == "숨은명소"


async def test_scoped_channel_prefers_my_region_then_backfills_nationally(db_session) -> None:
    await _seed_region(db_session, "26", "부산광역시")
    await _seed_region(db_session, "50", "제주특별자치도")
    await _seed_spot(db_session, "local1", title="부산 스팟", region="26", aesthetic=0.05)
    await _seed_buzz(db_session, "local1", scope="base", recent=0.9, blog_total=700)
    await _seed_spot(db_session, "far1", title="제주 스팟", region="50", aesthetic=0.3)
    await _seed_buzz(db_session, "far1", scope="base", recent=1.0, blog_total=90000)

    cards = await load_signal_channel_cached(db_session, FakeRedis(), "spot", region_cd="26")

    assert [c.content_id for c in cards] == ["local1", "far1"]


async def test_scoped_channel_spreads_within_the_region_by_sigungu(db_session) -> None:
    await _seed_region(db_session, "26", "부산광역시")
    for code, name in (("26380", "사하구"), ("26440", "강서구")):
        await db_session.execute(
            text(
                "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
                "VALUES (:c, '26', :n) ON CONFLICT DO NOTHING"
            ),
            {"c": code, "n": name},
        )
    for cid, sg, score in (("a1", "26380", 0.3), ("a2", "26380", 0.2), ("b1", "26440", 0.05)):
        await _seed_spot(db_session, cid, title=f"스팟-{cid}", region="26", aesthetic=score)
        await db_session.execute(
            text("UPDATE spots SET ldong_signgu_cd = :sg WHERE content_id = :cid"),
            {"sg": sg, "cid": cid},
        )
        await _seed_buzz(db_session, cid, scope="base", recent=1.0, blog_total=5000)

    cards = await load_signal_channel_cached(db_session, FakeRedis(), "spot", region_cd="26")

    assert {c.content_id for c in cards} >= {"a1", "b1"}
    assert "a2" not in {c.content_id for c in cards[:2]}


async def test_signal_channel_caches_in_redis(db_session) -> None:
    await _seed_region(db_session, "26", "부산광역시")
    await _seed_spot(db_session, "good", title="뜨는 곳", aesthetic=0.1)
    await _seed_buzz(db_session, "good", scope="base", recent=1.0, blog_total=5000)
    redis = FakeRedis()

    first = await load_signal_channel_cached(db_session, redis, "spot")
    await db_session.execute(text("DELETE FROM spot_buzz"))
    second = await load_signal_channel_cached(db_session, redis, "spot")

    assert first == second
