"""CHT — discover query + session state + heuristic LLM + turn orchestration + route."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.main import app
from app.modules.chat.llm import HeuristicChatLLM
from app.modules.chat.schemas import ChatTurnRequest
from app.modules.chat.services import run_turn
from app.modules.chat.state import (
    Condition,
    load_session,
    new_session,
    save_session,
)
from app.modules.spots.services.discover import (
    DiscoverFilters,
    discover_spots,
    pool_total,
    resolve_region,
)
from app.modules.spots.services.nearby import NearbyCategory

pytestmark = pytest.mark.anyio


async def _seed(
    session: AsyncSession,
    cid: str,
    *,
    title: str,
    l1: str = "NA",
    l2: str | None = None,
    l3: str | None = None,
    l3_nm: str | None = None,
    show: int = 1,
    img: str = "http://kto/i.jpg",
    overview: str | None = None,
    regn_cd: str = "51",
    regn_nm: str = "강원특별자치도",
    signgu_cd: str = "51150",
    signgu_nm: str = "강릉시",
    concentration: float | None = None,
) -> None:
    if l3 is not None:
        await session.execute(
            text(
                "INSERT INTO lcls_systm_codes (lcls_systm3_cd, lcls_systm2_cd, lcls_systm1_cd, "
                "lcls_systm3_nm) VALUES (:l3, :l2, :l1, :nm) ON CONFLICT DO NOTHING"
            ),
            {"l3": l3, "l2": l2, "l1": l1, "nm": l3_nm or l3},
        )
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
            "show_flag, mapx, mapy, lcls_systm1, lcls_systm2, lcls_systm3, "
            "ldong_regn_cd, ldong_signgu_cd) "
            "VALUES (:cid, 12, :t, :img, :show, 128.9, 37.75, :l1, :l2, :l3, :regn, :signgu)"
        ),
        {
            "cid": cid,
            "t": title,
            "img": img,
            "show": show,
            "l1": l1,
            "l2": l2,
            "l3": l3,
            "regn": regn_cd,
            "signgu": signgu_cd,
        },
    )
    if overview is not None:
        await session.execute(
            text(
                "INSERT INTO spot_details (content_id, content_type_id, overview) "
                "VALUES (:cid, 12, :ov) "
                "ON CONFLICT (content_id) DO UPDATE SET overview = :ov"
            ),
            {"cid": cid, "ov": overview},
        )
    if concentration is not None:
        await session.execute(
            text(
                "INSERT INTO spot_concentration "
                "(content_id, concentration_rate, base_ymd, raw_name) "
                "VALUES (:cid, :rate, '2026-07-19', :t) "
                "ON CONFLICT (content_id) DO UPDATE SET concentration_rate = :rate"
            ),
            {"cid": cid, "rate": concentration, "t": title},
        )


# ── discover query ────────────────────────────────────────────────────────


async def test_region_and_category_filter(db_session):
    await _seed(db_session, "c1", title="안목해변 카페", l1="FD", l2="FD05")
    await _seed(
        db_session,
        "c2",
        title="서울 카페",
        l1="FD",
        l2="FD05",
        regn_cd="11",
        regn_nm="서울특별시",
        signgu_cd="11110",
        signgu_nm="종로구",
    )
    await _seed(db_session, "c3", title="경포호 산책로", l1="NA")
    rows, total = await discover_spots(
        db_session,
        filters=DiscoverFilters(
            region_cd="51", sigungu_cd="51150", categories=(NearbyCategory.cafe,)
        ),
        limit=6,
    )
    assert total == 1
    assert rows[0].content_id == "c1"
    assert rows[0].region_label == "강원특별자치도 강릉시"


async def test_keyword_matches_title_or_overview(db_session):
    await _seed(
        db_session, "k1", title="솔향수목원", l1="NA", overview="금강소나무 숲길이 이어진다"
    )
    await _seed(db_session, "k2", title="중앙시장", l1="SH")
    rows, total = await discover_spots(
        db_session, filters=DiscoverFilters(region_cd="51", keywords=("숲길",)), limit=6
    )
    assert total == 1
    assert rows[0].content_id == "k1"
    assert rows[0].overview_head is not None


async def test_exclude_category_and_quiet_order(db_session):
    await _seed(db_session, "q1", title="한적한 해변", l1="NA", concentration=10)
    await _seed(db_session, "q2", title="붐비는 해변", l1="NA", concentration=90)
    await _seed(db_session, "q3", title="바닷가 카페", l1="FD", l2="FD05", concentration=5)
    rows, total = await discover_spots(
        db_session,
        filters=DiscoverFilters(
            region_cd="51", exclude_categories=(NearbyCategory.cafe,), quiet=True
        ),
        limit=6,
    )
    assert [r.content_id for r in rows] == ["q1", "q2"]
    assert total == 2
    assert rows[0].quiet is True
    assert rows[1].quiet is False


async def test_pool_total_counts_categorized(db_session):
    await _seed(db_session, "p1", title="관광지", l1="NA")
    await _seed(db_session, "p2", title="카페", l1="FD", l2="FD05")
    await _seed(db_session, "p3", title="숨김", l1="NA", show=0)
    assert await pool_total(db_session) == 2


async def test_resolve_region(db_session):
    await _seed(db_session, "r1", title="아무거나")
    assert await resolve_region(db_session, "강릉") == ("51", "51150", "강릉시")
    hit = await resolve_region(db_session, "강원")
    assert hit is not None and hit[0] == "51" and hit[1] is None
    assert await resolve_region(db_session, "존재불가지역") is None


# ── session state ─────────────────────────────────────────────────────────


async def test_session_roundtrip(redis_client_fake):
    s = new_session()
    s.turns = 2
    s.asked_axes = ["quiet"]
    s.conditions.append(
        Condition(
            id="region:51150", kind="region", label="강릉시", region_cd="51", sigungu_cd="51150"
        )
    )
    await save_session(redis_client_fake, s)
    loaded = await load_session(redis_client_fake, s.session_id)
    assert loaded is not None
    assert loaded.turns == 2
    assert loaded.asked_axes == ["quiet"]
    assert loaded.conditions[0].sigungu_cd == "51150"


async def test_load_missing_returns_none(redis_client_fake):
    assert await load_session(redis_client_fake, "nope") is None


def test_request_requires_action():
    with pytest.raises(ValueError):
        ChatTurnRequest(sessionId="x")
    ChatTurnRequest(utterance="강릉 카페")
    ChatTurnRequest(sessionId="x", skip=True)
    ChatTurnRequest(sessionId="x", removeConditionId="quiet")


# ── heuristic LLM ─────────────────────────────────────────────────────────


async def test_extract_category_region_keyword():
    r = await HeuristicChatLLM().extract("강릉 쪽으로 감성 카페 느낌", [])
    assert "cafe" in r.categories
    assert "강릉" in r.region_names
    assert "감성" in r.keywords


async def test_extract_exclusion_and_quiet():
    r = await HeuristicChatLLM().extract("카페 말고 한적하게 걷기 좋은 데", [])
    assert "cafe" in r.exclude_categories
    assert "cafe" not in r.categories
    assert r.quiet is True


# ── turn orchestration ────────────────────────────────────────────────────


async def test_first_turn_creates_session_and_board(db_session, redis_client_fake):
    await _seed(db_session, "s1", title="안목해변 카페", l1="FD", l2="FD05", overview="바다 정면")
    await _seed(db_session, "s2", title="경포호 산책로", l1="NA")
    res = await run_turn(
        db_session,
        redis_client_fake,
        ChatTurnRequest(utterance="강릉 카페"),
        llm=HeuristicChatLLM(),
    )
    assert res.sessionId
    assert res.candidateCount == 1
    assert res.poolTotal == 2
    assert res.cards[0].contentId == "s1"
    assert any("강릉" in c.label for c in res.conditions)
    # category already set -> board skips the category axis, asks quiet
    assert res.question == "사람 붐비는 건 어떠세요?"
    assert res.answers[0].kind == "ask"
    assert res.round == 2


async def test_second_turn_stacks_exclusion(db_session, redis_client_fake):
    await _seed(db_session, "s1", title="안목해변 카페", l1="FD", l2="FD05")
    await _seed(db_session, "s2", title="경포호 산책로", l1="NA", overview="걷기 좋은 호수")
    first = await run_turn(
        db_session,
        redis_client_fake,
        ChatTurnRequest(utterance="강릉 가볼만한 곳"),
        llm=HeuristicChatLLM(),
    )
    second = await run_turn(
        db_session,
        redis_client_fake,
        ChatTurnRequest(sessionId=first.sessionId, utterance="카페 말고 산책로"),
        llm=HeuristicChatLLM(),
    )
    assert second.sessionId == first.sessionId
    ids = [c.contentId for c in second.cards]
    assert "s1" not in ids and "s2" in ids
    assert any(c.exclude for c in second.conditions)


async def test_skip_advances_axis(db_session, redis_client_fake):
    await _seed(db_session, "s1", title="강릉 관광지", l1="NA")
    await _seed(db_session, "s2", title="강릉 명소", l1="HS")
    first = await run_turn(
        db_session,
        redis_client_fake,
        ChatTurnRequest(utterance="강릉"),
        llm=HeuristicChatLLM(),
    )
    q1 = first.question
    second = await run_turn(
        db_session,
        redis_client_fake,
        ChatTurnRequest(sessionId=first.sessionId, skip=True),
        llm=HeuristicChatLLM(),
    )
    assert second.question != q1


async def test_remove_condition_requeries(db_session, redis_client_fake):
    await _seed(db_session, "s1", title="안목해변 카페", l1="FD", l2="FD05")
    first = await run_turn(
        db_session,
        redis_client_fake,
        ChatTurnRequest(utterance="강릉 카페 말고"),
        llm=HeuristicChatLLM(),
    )
    target = next(c for c in first.conditions if c.exclude)
    res = await run_turn(
        db_session,
        redis_client_fake,
        ChatTurnRequest(sessionId=first.sessionId, removeConditionId=target.id),
        llm=HeuristicChatLLM(),
    )
    assert all(c.id != target.id for c in res.conditions)
    assert "s1" in [c.contentId for c in res.cards]


async def test_converged_offers_commit(db_session, redis_client_fake):
    await _seed(db_session, "s1", title="안목해변 카페", l1="FD", l2="FD05")
    first = await run_turn(
        db_session,
        redis_client_fake,
        ChatTurnRequest(utterance="강릉 카페"),
        llm=HeuristicChatLLM(),
    )
    second = await run_turn(
        db_session,
        redis_client_fake,
        ChatTurnRequest(sessionId=first.sessionId, skip=True),
        llm=HeuristicChatLLM(),
    )
    assert second.phase == "converged"
    assert second.answers[0].kind == "commit"


async def test_empty_phase_offers_remove(db_session, redis_client_fake):
    await _seed(db_session, "s1", title="안목해변 카페", l1="FD", l2="FD05")
    first = await run_turn(
        db_session,
        redis_client_fake,
        ChatTurnRequest(utterance="강릉 카페"),
        llm=HeuristicChatLLM(),
    )
    res = await run_turn(
        db_session,
        redis_client_fake,
        ChatTurnRequest(sessionId=first.sessionId, utterance="수영장딸린숙소"),
        llm=HeuristicChatLLM(),
    )
    assert res.phase == "empty"
    assert res.candidateCount == 0
    assert any(a.kind == "remove" for a in res.answers)


# ── route ─────────────────────────────────────────────────────────────────


async def test_chat_turn_endpoint(client, db_session, redis_client_fake):
    await _seed(db_session, "e1", title="안목해변 카페", l1="FD", l2="FD05")
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis_client_fake
    try:
        res = await client.post("/v1/chat/turn", json={"utterance": "강릉 카페"})
        assert res.status_code == 200
        body = res.json()
        assert body["error"] is None
        assert body["data"]["sessionId"]
        assert body["data"]["candidateCount"] == 1
        assert body["data"]["question"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_redis, None)


async def test_chat_turn_rejects_empty(client, db_session, redis_client_fake):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis_client_fake
    try:
        res = await client.post("/v1/chat/turn", json={})
        assert res.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_redis, None)
