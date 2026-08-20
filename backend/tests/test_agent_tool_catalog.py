from __future__ import annotations

import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent import repositories
from app.modules.agent.services import retrieve
from app.modules.agent.tools import CATALOG, ToolContext, schemas
from app.modules.agent.tools.base import describe

pytestmark = pytest.mark.asyncio


@pytest.fixture
def ctx(db_session: AsyncSession, redis_client_fake) -> ToolContext:
    return ToolContext(session=db_session, redis=redis_client_fake, kto=None)


async def _seed(session: AsyncSession, content_id: str, *, title: str, addr1: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, mapx, mapy) "
            "VALUES (:cid, 12, :t, :a, 'http://kto/i.jpg', 1, 'NA', 128.0, 35.0)"
        ),
        {"cid": content_id, "t": title, "a": addr1},
    )


async def test_every_tool_exposes_an_object_schema() -> None:
    declared = schemas()

    assert {tool["name"] for tool in declared} == set(CATALOG)
    for tool in declared:
        assert tool["parameters"]["type"] == "object"
        assert tool["description"]
        json.dumps(tool)


async def test_category_search_matches_the_service_it_wraps(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """어댑터가 기존 검색과 다른 결과를 내면 라우팅 전환이 회귀가 된다."""
    await _seed(db_session, "tc-1", title="통영 바다카페", addr1="경상남도 통영시 1")
    await _seed(db_session, "tc-2", title="서울 어딘가", addr1="서울특별시 중구 1")
    await db_session.flush()

    expected = await retrieve.search_candidates(
        db_session,
        repositories.CandidateQuery(limit=retrieve.CANDIDATE_LIMIT),
        preference="any",
        near=False,
    )

    result = await CATALOG["category_search"].run(ctx, {})

    assert [row.content_id for row in result.rows] == [row.content_id for row in expected]
    assert expected


async def test_title_search_matches_the_service_it_wraps(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    await _seed(db_session, "tt-1", title="통영 케이블카", addr1="경상남도 통영시 2")
    await db_session.flush()

    expected = await retrieve.search_by_title(db_session, ["케이블카"], region_prefixes=[])

    result = await CATALOG["title_search"].run(ctx, {"keywords": ["케이블카"]})

    assert [row.content_id for row in result.rows] == [row.content_id for row in expected]


async def test_missing_required_argument_returns_a_usable_observation(ctx: ToolContext) -> None:
    """빈 인자로 예외를 던지면 루프가 죽는다 — 모델이 고쳐 부를 수 있게 관찰로 돌려준다."""
    for name, args in (("title_search", {}), ("photo_match", {})):
        result = await CATALOG[name].run(ctx, args)
        assert result.rows == []
        assert "비었습니다" in result.observation


async def test_observation_caps_the_row_dump() -> None:
    rows = [
        repositories.CandidateRow(
            content_id=str(i),
            title=f"장소{i}",
            addr1=None,
            region_name="경상남도",
            sigungu_name="통영시",
            lat=None,
            lng=None,
            image_url=None,
            cpyrht_div_cd=None,
            concentration_rate=None,
        )
        for i in range(30)
    ]

    observation = describe(rows, empty="없음")

    assert observation.startswith("30곳:")
    assert "외 18곳" in observation
    assert observation.count("장소") == 12


@pytest.mark.parametrize("tool", ["category_search", "title_search", "photo_match"])
async def test_unmapped_region_does_not_become_a_nationwide_search(
    ctx: ToolContext, db_session: AsyncSession, tool: str
) -> None:
    """오타 하나가 전국 검색이 되면 모델이 지역을 고쳐 부를 기회를 잃는다."""
    await _seed(db_session, f"ur-{tool}", title="서울 어딘가", addr1="서울특별시 중구 9")
    await db_session.flush()

    result = await CATALOG[tool].run(
        ctx, {"regions": ["없는지역명xyz"], "keywords": ["어딘가"], "scene": "단풍"}
    )

    assert result.rows == []
    assert "지역으로 해석하지 못했습니다" in result.observation


async def test_food_categories_use_the_food_pool(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """카페·맛집은 FD 코드로 풀리는데 기본 후보 풀은 FD 를 뺀다 — 섞으면 항상 0곳이다."""
    called: dict[str, object] = {}

    async def spy(session, **kwargs):
        called.update(kwargs)
        return []

    from app.modules.agent.services import retrieve

    original = retrieve.search_food
    retrieve.search_food = spy
    try:
        await CATALOG["category_search"].run(ctx, {"categories": ["카페"], "regions": []})
    finally:
        retrieve.search_food = original

    assert called.get("action") == "cafe"


async def test_free_form_scene_is_normalised_not_crashed(ctx: ToolContext) -> None:
    """스키마 예시를 그대로 부르면 SCENE_PROMPTS[term] 이 KeyError 를 냈다."""
    result = await CATALOG["photo_match"].run(ctx, {"scene": "우주정거장"})

    assert result.rows == []
    assert "지원하지 않는 장면" in result.observation


async def test_scene_enum_only_advertises_supported_keys() -> None:
    from app.modules.agent.services import scene as scene_service

    declared = {tool["name"]: tool for tool in schemas()}
    allowed = declared["photo_match"]["parameters"]["properties"]["scene"]["enum"]

    assert set(allowed) == set(scene_service.SCENE_PROMPTS)


async def test_mood_is_an_axis_of_category_search_not_a_separate_tool() -> None:
    """분위기는 검색을 갈아타는 게 아니라 같은 검색을 좁히는 축이다."""
    declared = {tool["name"]: tool for tool in schemas()}

    assert "mood_search" not in declared
    moods = declared["category_search"]["parameters"]["properties"]["moods"]
    assert "sea" in moods["items"]["enum"]


async def test_unknown_mood_is_dropped(ctx: ToolContext, db_session: AsyncSession) -> None:
    await _seed(db_session, "tm-1", title="바다 전망대", addr1="경상남도 통영시 3")
    await db_session.flush()

    result = await CATALOG["category_search"].run(
        ctx, {"regions": ["통영"], "moods": ["sea", "nonsense"]}
    )

    assert isinstance(result.rows, list)


async def test_labels_render_for_every_tool() -> None:
    assert CATALOG["category_search"].label({"categories": ["카페"]}) == "카페 관광지 조회"
    assert CATALOG["category_search"].label({"indoor": True}) == "실내 관광지 조회"
    assert CATALOG["category_search"].label({}) == "전국 관광지 조회"
    assert CATALOG["title_search"].label({"keywords": ["케이블카"]}) == "케이블카 이름으로 조회"
    assert CATALOG["photo_match"].label({"scene": "노을"}) == "노을 사진으로 찾기"


async def test_nearby_without_an_anchor_or_coords_asks_for_one(ctx: ToolContext) -> None:
    result = await CATALOG["nearby"].run(ctx, {})

    assert result.rows == []
    assert "contentId" in result.observation


async def test_nearby_excludes_the_anchor_itself(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    await _seed(db_session, "an-1", title="기준지", addr1="경상남도 통영시 10")
    await _seed(db_session, "an-2", title="옆집", addr1="경상남도 통영시 11")
    await db_session.flush()

    result = await CATALOG["nearby"].run(ctx, {"contentId": "an-1"})

    assert "an-1" not in [row.content_id for row in result.rows]


async def test_related_without_an_embedding_says_so(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """임베딩이 없으면 예외가 아니라 관찰로 알려야 모델이 다른 도구로 넘어간다."""
    await _seed(db_session, "rl-1", title="임베딩없는곳", addr1="경상남도 통영시 12")
    await db_session.flush()

    result = await CATALOG["related"].run(ctx, {"contentId": "rl-1"})

    assert result.rows == []
    assert "임베딩" in result.observation


async def test_concentration_reports_a_single_spot(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    await _seed(db_session, "cn-1", title="혼잡도없는곳", addr1="경상남도 통영시 13")
    await db_session.flush()

    result = await CATALOG["concentration"].run(ctx, {"contentId": "cn-1"})

    assert [row.content_id for row in result.rows] == ["cn-1"]
    assert "혼잡도" in result.observation


async def test_unknown_content_id_never_raises(ctx: ToolContext) -> None:
    for name in ("nearby", "related", "concentration"):
        result = await CATALOG[name].run(ctx, {"contentId": "does-not-exist"})
        assert result.rows == []
        assert result.observation
