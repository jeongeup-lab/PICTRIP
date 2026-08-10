from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.main import app
from scripts.sync_shorts import (
    parse_duration_sec,
    rank_feed,
    short_region_name,
    title_variants,
)


async def _seed_spot(
    session: AsyncSession,
    cid: str,
    *,
    title: str,
    regn_cd: str = "11",
    regn_nm: str = "서울특별시",
    signgu_cd: str = "11110",
    signgu_nm: str = "종로구",
    img: str | None = "http://tong.visitkorea.or.kr/cms/i.jpg",
) -> None:
    await session.execute(
        text(
            "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES (:cd, :nm) "
            "ON CONFLICT DO NOTHING"
        ),
        {"cd": regn_cd, "nm": regn_nm},
    )
    await session.execute(
        text(
            "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
            "VALUES (:cd, :regn, :nm) ON CONFLICT DO NOTHING"
        ),
        {"cd": signgu_cd, "regn": regn_cd, "nm": signgu_nm},
    )
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, mapx, mapy, ldong_regn_cd, ldong_signgu_cd) "
            "VALUES (:cid, 12, :t, :img, 1, 126.97, 37.57, :regn, :signgu)"
        ),
        {"cid": cid, "t": title, "img": img, "regn": regn_cd, "signgu": signgu_cd},
    )


async def _seed_short(
    session: AsyncSession,
    video_id: str,
    *,
    rank: int,
    anchor: str = "경주",
    views: int = 1000,
    spot_ids: list[str] | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO travel_shorts (video_id, title, channel_title, thumbnail_url, "
            "view_count, duration_sec, published_at, anchor_label, rank) "
            "VALUES (:vid, :title, :ch, :thumb, :views, 60, now(), :anchor, :rank)"
        ),
        {
            "vid": video_id,
            "title": f"title-{video_id}",
            "ch": f"ch-{video_id}",
            "thumb": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            "views": views,
            "anchor": anchor,
            "rank": rank,
        },
    )
    for spot_rank, cid in enumerate(spot_ids or [], start=1):
        await session.execute(
            text(
                "INSERT INTO travel_shorts_spots (video_id, content_id, rank) "
                "VALUES (:vid, :cid, :rank)"
            ),
            {"vid": video_id, "cid": cid, "rank": spot_rank},
        )


@pytest.fixture
async def seeded_shorts(db_session):
    await _seed_spot(db_session, "c-1", title="경복궁")
    await _seed_spot(db_session, "c-2", title="북촌한옥마을", img=None)
    await _seed_short(db_session, "vid00000001", rank=1, views=90000, spot_ids=["c-1", "c-2"])
    await _seed_short(db_session, "vid00000002", rank=2, views=50000, spot_ids=["c-1"])
    await _seed_short(db_session, "vid00000003", rank=3, views=10000, spot_ids=[])
    await db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.clear()


async def test_shorts_page_shape_and_order(client, seeded_shorts):
    res = await client.get("/v1/shorts", params={"limit": 2})
    body = res.json()
    assert res.status_code == 200 and body["error"] is None
    data = body["data"]
    assert [item["videoId"] for item in data["items"]] == ["vid00000001", "vid00000002"]
    assert data["hasMore"] is True and data["nextCursor"] == "2"
    first = data["items"][0]
    assert {
        "videoId",
        "title",
        "channelTitle",
        "thumbnailUrl",
        "viewCount",
        "anchorLabel",
        "spots",
    } <= set(first)
    assert first["viewCount"] == 90000
    spot = first["spots"][0]
    assert spot["contentId"] == "c-1"
    assert spot["title"] == "경복궁"
    assert spot["regionLabel"] == "서울특별시 종로구"
    assert spot["imageUrl"]


async def test_shorts_cursor_pagination(client, seeded_shorts):
    res = await client.get("/v1/shorts", params={"limit": 2, "cursor": "2"})
    data = res.json()["data"]
    assert [item["videoId"] for item in data["items"]] == ["vid00000003"]
    assert data["hasMore"] is False and data["nextCursor"] is None
    assert data["items"][0]["spots"] == []


async def test_shorts_invalid_cursor_is_422(client, seeded_shorts):
    res = await client.get("/v1/shorts", params={"cursor": "abc"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"


async def test_shorts_empty_table(client, db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        res = await client.get("/v1/shorts")
        data = res.json()["data"]
        assert data["items"] == [] and data["hasMore"] is False
    finally:
        app.dependency_overrides.clear()


def test_parse_duration_sec():
    assert parse_duration_sec("PT58S") == 58
    assert parse_duration_sec("PT1M20S") == 80
    assert parse_duration_sec("PT1H2M3S") == 3723
    assert parse_duration_sec("") == 0
    assert parse_duration_sec("bogus") == 0


def test_short_region_name():
    assert short_region_name("경주시") == "경주"
    assert short_region_name("해운대구") == "해운대"
    assert short_region_name("중구") is None
    assert short_region_name("가평군") == "가평"


def test_title_variants():
    assert title_variants("천마총(대릉원)") == ["천마총(대릉원)", "천마총"]
    assert title_variants("경복궁") == ["경복궁"]


def test_rank_feed_caps_per_anchor_and_sorts_by_views():
    from datetime import UTC, datetime

    from scripts.sync_shorts import ShortCandidate

    def make(video_id: str, views: int, anchor: str) -> ShortCandidate:
        candidate = ShortCandidate(
            video_id=video_id,
            title="t",
            channel_title="c",
            thumbnail_url="u",
            view_count=views,
            duration_sec=60,
            published_at=datetime.now(UTC),
            query_sigungu=None,
        )
        candidate.anchor_label = anchor
        return candidate

    candidates = [make(f"v{i}", views=i * 10, anchor="부산") for i in range(1, 6)]
    candidates.append(make("gj", views=5, anchor="경주"))
    ranked = rank_feed(candidates)
    busan = [c for c in ranked if c.anchor_label == "부산"]
    assert len(busan) == 3
    assert [c.video_id for c in busan] == ["v5", "v4", "v3"]
    assert ranked[-1].video_id == "gj"


def test_merge_places_text_enables_broad_resolution():
    from datetime import UTC, datetime

    from scripts.sync_shorts import (
        ShortCandidate,
        SigunguEntry,
        merge_places_text,
        resolve_broad_sigungu,
    )

    pool = [
        SigunguEntry(code="47130", name="경주시", short_name="경주", lat=35.8, lng=129.2),
    ]
    candidate = ShortCandidate(
        video_id="v1",
        title="숨은 국내 여행지 TOP10",
        channel_title="c",
        thumbnail_url="u",
        view_count=100,
        duration_sec=60,
        published_at=datetime.now(UTC),
        query_sigungu=None,
    )
    assert resolve_broad_sigungu(candidate, pool) is None
    merge_places_text(candidate, ["  경주 대릉원 ", "", None if False else "첨성대"])
    assert "경주" in candidate.description
    resolved = resolve_broad_sigungu(candidate, pool)
    assert resolved is not None and resolved.short_name == "경주"
