from __future__ import annotations

import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent import repositories, toolloop
from app.modules.agent.routing import ToolCall
from app.modules.agent.services import retrieve
from app.modules.agent.tools import CATALOG, ToolContext, itinerary, schemas
from app.modules.agent.tools.base import describe
from app.modules.spots import categories

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

    placed = ToolContext(session=db_session, redis=ctx.redis, kto=None, lat=37.0, lng=127.0)
    expected = await retrieve.search_candidates(
        db_session,
        repositories.CandidateQuery(limit=retrieve.CANDIDATE_LIMIT, lat=37.0, lng=127.0),
        preference="any",
        near=True,
    )

    result = await CATALOG["category_search"].run(placed, {"near": True})

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


async def test_concentration_reports_a_single_spot_without_counting_it_as_a_result(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    await _seed(db_session, "cn-1", title="혼잡도없는곳", addr1="경상남도 통영시 13")
    await db_session.flush()

    result = await CATALOG["concentration"].run(ctx, {"contentId": "cn-1"})

    assert result.rows == []
    assert [row.content_id for row in result.anchors] == ["cn-1"]
    assert "혼잡도" in result.observation


async def test_unknown_content_id_never_raises(ctx: ToolContext) -> None:
    for name in ("nearby", "related", "concentration"):
        result = await CATALOG[name].run(ctx, {"contentId": "does-not-exist"})
        assert result.rows == []
        assert result.observation


async def test_resolve_place_needs_a_name(ctx: ToolContext) -> None:
    result = await CATALOG["resolve_place"].run(ctx, {})

    assert result.rows == []
    assert "names" in result.observation


async def test_resolve_place_reports_what_it_could_not_find(ctx: ToolContext) -> None:
    """못 찾았을 때 이름을 되돌려줘야 모델이 일반 검색으로 갈아탈지 정한다."""
    result = await CATALOG["resolve_place"].run(ctx, {"names": ["없는장소이름xyz"]})

    assert result.rows == []
    assert "없는장소이름xyz" in result.observation


async def test_resolve_place_advertises_the_boundary_against_common_nouns() -> None:
    declared = {tool["name"]: tool for tool in schemas()}

    description = declared["resolve_place"]["description"]
    assert "일반명사" in description
    assert "지역명" in description


async def test_catalog_covers_every_real_tool() -> None:
    """스텝 표시(mood_search·intent)는 도구가 아니다 — 모델에게 없는 선택지를 주면 안 된다."""
    assert set(CATALOG) == {
        "category_search",
        "title_search",
        "photo_match",
        "nearby",
        "related",
        "concentration",
        "resolve_place",
        "spot_detail",
        "festival",
        "compare_regions",
        "region_profile",
        "similar_region",
        "uploaded_photo",
        "plan_itinerary",
        "from_saved",
    }


async def test_spot_detail_needs_a_content_id(ctx: ToolContext) -> None:
    result = await CATALOG["spot_detail"].run(ctx, {})

    assert result.rows == []
    assert "contentId" in result.observation


async def test_spot_detail_says_when_kto_has_not_answered_yet(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """자료가 없다는 걸 알려야 모델이 없는 사실을 지어내지 않는다."""
    await _seed(db_session, "sd-1", title="자료없는곳", addr1="서울특별시 중구 5")
    await db_session.flush()

    result = await CATALOG["spot_detail"].run(ctx, {"contentId": "sd-1", "fields": ["parking"]})

    assert "자료없는곳" in result.observation
    assert "다른 곳으로 답하세요" in result.observation


async def test_festival_unavailability_is_not_swallowed(ctx: ToolContext) -> None:
    """삼키면 축제 질문에 엉뚱한 스팟이 간다 — 모바일은 err.code 로 분기한다."""
    from app.modules.agent.errors import AgentFestivalUnavailable

    with pytest.raises(AgentFestivalUnavailable):
        await CATALOG["festival"].run(ctx, {})


@pytest.mark.parametrize("tool", ["spot_detail", "nearby", "related", "concentration"])
async def test_a_title_passed_as_a_content_id_never_leaks_an_internal_error(
    ctx: ToolContext, tool: str
) -> None:
    """모델이 contentId 자리에 제목을 넣으면 ResourceNotFound 가 답변으로 샜다."""
    result = await CATALOG[tool].run(ctx, {"contentId": "클라우드힐"})

    assert result.rows == []
    assert "not found" not in result.observation
    assert "contentId" in result.observation


async def test_compare_regions_needs_two_regions(ctx: ToolContext) -> None:
    result = await CATALOG["compare_regions"].run(ctx, {"regions": ["부산"]})

    assert result.rows == []
    assert "둘 이상" in result.observation


async def test_compare_regions_reports_each_side_separately(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """한쪽만 검색하면 "여수는 결과가 안 잡혀서" 로 끝난다 — 실제로 그랬다."""
    result = await CATALOG["compare_regions"].run(ctx, {"regions": ["없는곳A", "없는곳B"]})

    assert result.observation.count("|") == 1
    assert "없는곳A" in result.observation
    assert "없는곳B" in result.observation


async def test_compare_regions_caps_how_many_it_compares(ctx: ToolContext) -> None:
    many = [f"지역{i}" for i in range(6)]

    result = await CATALOG["compare_regions"].run(ctx, {"regions": many})

    assert result.observation.count("|") == 2


async def test_compare_regions_labels_the_step_with_both_sides() -> None:
    assert CATALOG["compare_regions"].label({"regions": ["부산", "여수"]}) == "부산 vs 여수 비교"


async def test_region_profile_needs_a_region(ctx: ToolContext) -> None:
    result = await CATALOG["region_profile"].run(ctx, {})

    assert result.rows == []
    assert "regions" in result.observation


async def test_region_profile_says_when_it_cannot_place_the_name(ctx: ToolContext) -> None:
    """지역 해석 실패를 전국 요약으로 바꾸면 엉뚱한 도시를 설명한다."""
    result = await CATALOG["region_profile"].run(ctx, {"regions": ["없는곳xyz"]})

    assert result.rows == []
    assert "지역으로 해석하지 못했습니다" in result.observation


async def test_region_profile_caps_the_cards_it_returns(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """요약은 목록이 아니다 — 400곳을 카드로 쏟으면 답변이 검색처럼 보인다."""
    for i in range(12):
        await _seed(db_session, f"rp-{i}", title=f"곳{i}", addr1="서울특별시 중구 7")
    await db_session.flush()

    result = await CATALOG["region_profile"].run(ctx, {"regions": []})

    assert result.rows == []


async def test_region_profile_labels_the_step_with_the_place() -> None:
    assert CATALOG["region_profile"].label({"regions": ["전주"]}) == "전주 살펴보기"


async def _seed_embedded(
    session: AsyncSession, content_id: str, *, title: str, addr1: str, tilt: float
) -> None:
    await _seed(session, content_id, title=title, addr1=addr1)
    vector = "[" + ",".join(f"{tilt if i == 0 else 0.1:.4f}" for i in range(512)) + "]"
    await session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, image_url, embedding) "
            "VALUES (:cid, 'http://kto/i.jpg', CAST(:v AS halfvec(512)))"
        ),
        {"cid": content_id, "v": vector},
    )


async def test_similar_region_needs_a_region(ctx: ToolContext) -> None:
    result = await CATALOG["similar_region"].run(ctx, {})

    assert result.rows == []
    assert "regions" in result.observation


async def test_similar_region_says_when_the_place_has_no_embeddings(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """씨앗을 혼잡도로 고르면 임베딩 없는 곳이 잡힌다 — 실제로 그랬다."""
    await _seed(db_session, "sr-noemb", title="임베딩없음", addr1="서울특별시 중구 21")
    await db_session.flush()

    result = await CATALOG["similar_region"].run(ctx, {"regions": ["서울"]})

    assert result.rows == []
    assert "임베딩" in result.observation


async def test_similar_region_excludes_the_source_region(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """같은 지역을 돌려주면 "닮은 다른 지역" 이 아니라 그냥 검색이다."""
    await _seed_embedded(db_session, "sr-src", title="기준지", addr1="서울특별시 중구 22", tilt=0.9)
    await _seed_embedded(
        db_session, "sr-same", title="같은지역", addr1="서울특별시 중구 23", tilt=0.9
    )
    await db_session.flush()

    result = await CATALOG["similar_region"].run(ctx, {"regions": ["서울"]})

    assert [row.content_id for row in result.rows] == []


async def test_similar_region_finds_another_sido(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    await _seed_embedded(db_session, "sr-a", title="서울기준", addr1="서울특별시 중구 31", tilt=0.9)
    await _seed_embedded(
        db_session, "sr-b", title="부산닮은곳", addr1="부산광역시 해운대구 1", tilt=0.9
    )
    await _seed_embedded(
        db_session, "sr-c", title="제주먼곳", addr1="제주특별자치도 제주시 1", tilt=-0.9
    )
    await db_session.flush()

    result = await CATALOG["similar_region"].run(ctx, {"regions": ["서울"]})

    assert "sr-b" in [row.content_id for row in result.rows], result.observation
    assert "sr-a" not in [row.content_id for row in result.rows]
    assert "부산" in result.observation


async def _seed_at(
    session: AsyncSession, content_id: str, *, title: str, lat: float, lng: float
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, mapx, mapy) "
            "VALUES (:cid, 12, :t, '서울특별시 중구 9', 'http://kto/i.jpg', 1, 'NA', :x, :y)"
        ),
        {"cid": content_id, "t": title, "x": lng, "y": lat},
    )


async def test_plan_itinerary_needs_a_region(ctx: ToolContext) -> None:
    result = await CATALOG["plan_itinerary"].run(ctx, {})

    assert result.rows == []
    assert "regions" in result.observation


async def test_plan_itinerary_caps_the_days(ctx: ToolContext, db_session: AsyncSession) -> None:
    for i in range(20):
        await _seed_at(db_session, f"pi-{i}", title=f"곳{i}", lat=37.5 + i * 0.001, lng=127.0)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(ctx, {"regions": ["서울"], "days": 99})

    assert result.observation.count("일차:") <= 4


async def test_plan_itinerary_drops_a_spot_that_sits_far_from_the_cluster(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """좌표가 지역과 안 맞는 스팟이 실제로 있다 — 경주 황성공원이 춘천 좌표를 달고 있었다."""
    for i in range(5):
        await _seed_at(db_session, f"pc-{i}", title=f"가까운{i}", lat=37.56 + i * 0.002, lng=126.98)
    await _seed_at(db_session, "pc-far", title="멀리떨어진곳", lat=35.8, lng=129.5)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(ctx, {"regions": ["서울"], "days": 2})

    assert "멀리떨어진곳" not in result.observation


async def test_plan_itinerary_orders_by_nearest_hop(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """되돌아가는 동선이면 일정이 아니라 목록이다. 시작점은 검색 순서가 정한다."""
    for cid, lat in (("po-a", 37.50), ("po-b", 37.52), ("po-c", 37.54)):
        await _seed_at(db_session, cid, title=cid, lat=lat, lng=127.0)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(ctx, {"regions": ["서울"], "days": 1})

    ordered = [row.content_id for row in result.rows][:3]
    assert ordered in (["po-a", "po-b", "po-c"], ["po-c", "po-b", "po-a"])


async def _seed_food(session: AsyncSession, content_id: str, *, title: str, lat: float) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, lcls_systm2, mapx, mapy) "
            "VALUES (:cid, 39, :t, '서울특별시 중구 9', 'http://kto/i.jpg', 1, 'FD', 'FD01', "
            "127.0, :y)"
        ),
        {"cid": content_id, "t": title, "y": lat},
    )


async def test_plan_itinerary_keeps_restaurants_out_of_the_travel_pool(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """기본 여행지 풀은 FD 를 제외한다 — 맛집 일정이 조용히 0곳이 되면 안 된다."""
    for i in range(6):
        await _seed_food(db_session, f"pf-{i}", title=f"밥집{i}", lat=37.5 + i * 0.002)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(
        ctx, {"regions": ["서울"], "days": 1, "categories": ["맛집"]}
    )

    assert result.rows
    assert "밥집" in result.observation


async def test_plan_itinerary_puts_one_meal_in_each_day(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    for i in range(8):
        await _seed_at(db_session, f"pm-{i}", title=f"볼거리{i}", lat=37.5 + i * 0.002, lng=127.0)
    for i in range(3):
        await _seed_food(db_session, f"pmf-{i}", title=f"밥집{i}", lat=37.5 + i * 0.002)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(
        ctx, {"regions": ["서울"], "days": 2, "categories": ["관광지", "맛집"]}
    )

    for line in result.observation.split(" / "):
        assert sum(name.startswith("밥집") for name in line.split(" → ")) <= 1
    assert result.observation.count("밥집") == 2


async def test_plan_itinerary_hands_the_plan_to_the_answer(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """카드 순서만으로는 일차 구분과 이동 거리를 복원할 수 없다."""
    for i in range(6):
        await _seed_at(db_session, f"pw-{i}", title=f"곳{i}", lat=37.5 + i * 0.002, lng=127.0)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(ctx, {"regions": ["서울"], "days": 2})

    assert result.fact == result.observation


async def _seed_cafe(session: AsyncSession, content_id: str, *, title: str, lat: float) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, lcls_systm2, mapx, mapy) "
            "VALUES (:cid, 39, :t, '서울특별시 중구 9', 'http://kto/i.jpg', 1, 'FD', 'FD05', "
            "127.0, :y)"
        ),
        {"cid": content_id, "t": title, "y": lat},
    )


async def test_plan_itinerary_gives_every_requested_food_kind_a_slot(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """거리만 보고 고르면 가까운 식당이 모든 날을 채우고 카페가 사라진다."""
    for i in range(6):
        await _seed_at(db_session, f"pk-{i}", title=f"볼거리{i}", lat=37.5 + i * 0.002, lng=127.0)
    for i in range(4):
        await _seed_food(db_session, f"pk-food-{i}", title=f"밥집{i}", lat=37.5 + i * 0.001)
        await _seed_cafe(db_session, f"pk-cafe-{i}", title=f"찻집{i}", lat=37.5 + i * 0.001)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(
        ctx, {"regions": ["서울"], "days": 2, "categories": ["맛집", "카페"]}
    )

    for line in result.observation.split(" / "):
        names = line.split(" → ")
        assert any(name.startswith("밥집") for name in names)
        assert any(name.startswith("찻집") for name in names)


async def test_plan_itinerary_plans_the_first_region_only(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """두 지역을 한 군집으로 합치면 이상치 제거가 한 지역을 통째로 지운다."""
    for i in range(6):
        await _seed_at(db_session, f"pr-{i}", title=f"서울{i}", lat=37.5 + i * 0.002, lng=127.0)
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, mapx, mapy) "
            "VALUES ('pr-far', 12, '부산곳', '부산광역시 해운대구 1', 'http://kto/i.jpg', 1, "
            "'NA', 129.16, 35.16)"
        )
    )
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(ctx, {"regions": ["서울", "부산"], "days": 1})

    assert "부산곳" not in result.observation


async def test_a_chip_on_an_itinerary_replans_instead_of_searching_the_country() -> None:
    """일정 조건이 intent 에 없으면 칩 한 번에 지역과 일수를 다 잃는다."""
    call = ToolCall(name="plan_itinerary", args={"regions": ["통영"], "days": 3})

    intent = toolloop.intent_of([call])
    replay = toolloop.call_from_intent(intent)

    assert intent.days == 3
    assert replay.name == "plan_itinerary"
    assert replay.args["regions"] == ["통영"]
    assert replay.args["days"] == 3


async def test_an_itinerary_stores_the_days_it_actually_used() -> None:
    """원시 인자를 그대로 저장하면 기본값 2일 일정이 intent 에서 사라진다."""
    call = ToolCall(name="plan_itinerary", args={"regions": ["통영"]})

    assert toolloop.intent_of([call]).days == 2


async def test_an_itinerary_offers_only_chips_it_can_honour() -> None:
    """지역을 지우면 일정은 'regions 가 비었습니다' 로 끝난다."""
    call = ToolCall(name="plan_itinerary", args={"regions": ["통영"]})
    trace = toolloop.Trace(
        rows=[
            repositories.CandidateRow(
                content_id=str(i),
                title=f"장소{i}",
                addr1="경상남도 통영시 1",
                region_name="경상남도",
                sigungu_name="통영시",
                lat=34.85,
                lng=128.43,
                image_url=None,
                cpyrht_div_cd=None,
                concentration_rate=None,
            )
            for i in range(9)
        ],
        calls_made=[call],
    )

    response = toolloop.respond(trace, lat=37.5, lng=127.0)

    assert [chip.label for chip in response.refinements] == ["사람 적은 곳만"]


async def test_plan_itinerary_keeps_the_dish_the_user_named(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """'부산 국밥 2일' 이 아무 식당이나 내놓으면 요청을 버린 것이다."""
    for i in range(6):
        await _seed_at(db_session, f"pd-{i}", title=f"볼거리{i}", lat=37.5 + i * 0.002, lng=127.0)
    await _seed_food(db_session, "pd-hit", title="할매국밥", lat=37.501)
    await _seed_food(db_session, "pd-miss", title="파스타집", lat=37.502)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(
        ctx, {"regions": ["서울"], "days": 1, "categories": ["국밥"]}
    )

    assert "할매국밥" in result.observation
    assert "파스타집" not in result.observation


async def test_plan_itinerary_pools_each_named_dish_apart(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """제목 조건이 AND 라 한 풀에 두 음식명을 넣으면 교집합이 비어 둘 다 사라진다."""
    for i in range(6):
        await _seed_at(db_session, f"pp-{i}", title=f"볼거리{i}", lat=37.5 + i * 0.002, lng=127.0)
    await _seed_food(db_session, "pp-a", title="할매국밥", lat=37.501)
    await _seed_food(db_session, "pp-b", title="초밥명가", lat=37.502)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(
        ctx, {"regions": ["서울"], "days": 1, "categories": ["국밥", "초밥"]}
    )

    assert "할매국밥" in result.observation
    assert "초밥명가" in result.observation


async def test_plan_itinerary_says_when_it_could_not_fill_the_days(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """4일을 요청했는데 1일을 조용히 돌려주면 못 채운 사실이 사라진다."""
    for i in range(3):
        await _seed_at(db_session, f"ps-{i}", title=f"드문곳{i}", lat=37.5 + i * 0.002, lng=127.0)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(ctx, {"regions": ["서울"], "days": 4})

    assert "요청한 4일" in result.observation


async def test_plan_itinerary_still_plans_with_three_food_kinds(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """음식 슬롯이 하루 정원을 넘으면 볼거리 자리가 0이 되어 일정이 통째로 비었다."""
    for i in range(6):
        await _seed_at(db_session, f"p3-{i}", title=f"볼거리{i}", lat=37.5 + i * 0.002, lng=127.0)
    await _seed_food(db_session, "p3-food", title="밥집하나", lat=37.501)
    await _seed_food(db_session, "p3-dish", title="할매국밥", lat=37.502)
    await _seed_cafe(db_session, "p3-cafe", title="찻집하나", lat=37.503)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(
        ctx, {"regions": ["서울"], "days": 2, "categories": ["맛집", "카페", "국밥"]}
    )

    assert result.observation.count("일차:") == 2


async def test_plan_itinerary_never_books_one_place_twice(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """맛집 풀과 국밥 풀은 겹친다 — 같은 국밥집이 한 날에 두 번 들어갔다."""
    for i in range(6):
        await _seed_at(db_session, f"p2-{i}", title=f"볼거리{i}", lat=37.5 + i * 0.002, lng=127.0)
    await _seed_food(db_session, "p2-only", title="할매국밥", lat=37.501)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(
        ctx, {"regions": ["서울"], "days": 1, "categories": ["맛집", "국밥"]}
    )

    ids = [row.content_id for row in result.rows]
    assert len(ids) == len(set(ids))


async def test_plan_itinerary_says_which_food_it_could_not_find(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """국밥집이 없는데 관광지만 돌려주면 요청을 조용히 버린 것이다."""
    for i in range(6):
        await _seed_at(db_session, f"p1-{i}", title=f"볼거리{i}", lat=37.5 + i * 0.002, lng=127.0)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(
        ctx, {"regions": ["서울"], "days": 1, "categories": ["국밥"]}
    )

    assert "국밥: 그 지역에서 찾지 못했습니다" in result.observation


async def test_plan_itinerary_never_exceeds_the_daily_capacity(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """하루가 정원을 넘으면 카드 20개 밖 장소가 일정 문장에만 나온다."""
    for i in range(9):
        await _seed_at(db_session, f"pc2-{i}", title=f"볼거리{i}", lat=37.5 + i * 0.002, lng=127.0)
    for i in range(4):
        await _seed_food(db_session, f"pc2-f{i}", title=f"밥집{i}", lat=37.5 + i * 0.001)
        await _seed_cafe(db_session, f"pc2-c{i}", title=f"찻집{i}", lat=37.5 + i * 0.001)
    await _seed_food(db_session, "pc2-d", title="할매국밥", lat=37.502)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(
        ctx, {"regions": ["서울"], "days": 2, "categories": ["맛집", "카페", "국밥"]}
    )

    for line in result.observation.split(" / "):
        assert len(line.split(" → ")) <= 3


async def test_plan_itinerary_reports_a_food_kind_it_ran_out_of(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """카페가 한 곳뿐인 2일 일정은 둘째 날 카페를 조용히 뺐다."""
    for i in range(6):
        await _seed_at(db_session, f"pe-{i}", title=f"볼거리{i}", lat=37.5 + i * 0.002, lng=127.0)
    await _seed_cafe(db_session, "pe-cafe", title="찻집하나", lat=37.501)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(
        ctx, {"regions": ["서울"], "days": 2, "categories": ["카페"]}
    )

    assert "카페: 하루 자리가 모자라" in result.observation


async def test_plan_itinerary_marks_shopping_codes_as_outside_the_travel_pool() -> None:
    """여행지 풀은 LS·SH 를 제외한다 — 코드만 걸면 쇼핑 일정이 조용히 0곳이 된다."""
    assert itinerary._outside_pool(["SH01", "SH02"])
    assert itinerary._outside_pool(["LS03"])
    assert not itinerary._outside_pool(["NA01", "SH01"])


async def test_plan_itinerary_reports_a_food_kind_it_never_got_to(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """1일 일정에 음식 세 종류면 셋째는 후보가 있어도 자리를 못 받는다."""
    for i in range(6):
        await _seed_at(db_session, f"pn-{i}", title=f"볼거리{i}", lat=37.5 + i * 0.002, lng=127.0)
    await _seed_food(db_session, "pn-f", title="밥집하나", lat=37.501)
    await _seed_food(db_session, "pn-d", title="할매국밥", lat=37.502)
    await _seed_cafe(db_session, "pn-c", title="찻집하나", lat=37.503)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(
        ctx, {"regions": ["서울"], "days": 1, "categories": ["맛집", "카페", "국밥"]}
    )

    assert "하루 자리가 모자라" in result.observation


async def test_plan_itinerary_never_repeats_a_place_in_a_food_only_region(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """볼거리가 없는 지역에서는 맛집 풀과 국밥 풀이 그대로 겹쳐 들어갔다."""
    await _seed_food(db_session, "pz-a", title="할매국밥", lat=37.501)
    await _seed_food(db_session, "pz-b", title="옆집국밥", lat=37.502)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(
        ctx, {"regions": ["서울"], "days": 1, "categories": ["맛집", "국밥"]}
    )

    ids = [row.content_id for row in result.rows]
    assert len(ids) == len(set(ids))


async def test_plan_itinerary_keeps_food_kinds_apart_without_any_sights(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """볼거리가 없는 지역에서 음식을 한 목록으로 합치면 카페가 통째로 밀려난다."""
    for i in range(6):
        await _seed_food(db_session, f"pv-f{i}", title=f"밥집{i}", lat=37.5 + i * 0.001)
    await _seed_cafe(db_session, "pv-c", title="찻집하나", lat=37.502)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(
        ctx, {"regions": ["서울"], "days": 1, "categories": ["맛집", "카페"]}
    )

    assert "찻집하나" in result.observation


async def test_plan_itinerary_says_when_a_sight_category_found_nothing(
    ctx: ToolContext, db_session: AsyncSession
) -> None:
    """박물관을 못 찾아 식당만 남은 일정을 성공으로 돌려주면 요청을 버린 것이다."""
    await _seed_food(db_session, "pg-a", title="밥집하나", lat=37.501)
    await _seed_food(db_session, "pg-b", title="밥집둘", lat=37.502)
    await db_session.flush()

    result = await CATALOG["plan_itinerary"].run(
        ctx, {"regions": ["서울"], "days": 1, "categories": ["박물관", "맛집"]}
    )

    assert "박물관: 그 지역에서 찾지 못했습니다" in result.observation


async def test_plan_itinerary_asks_for_a_region_instead_of_failing(ctx: ToolContext) -> None:
    """지역 없이 부르면 '조건에 맞는 곳을 찾지 못했어요' 로 끝나 이유가 사라진다."""
    result = await CATALOG["plan_itinerary"].run(ctx, {})

    assert result.rows == []
    assert result.fact is not None and "어느 지역" in result.fact


async def test_a_smalltalk_turn_never_shows_the_router_thinking_out_loud() -> None:
    """라우터가 뱉은 텍스트를 답으로 쓰면 '도구를 부르지 않고 되묻는다' 가 화면에 나온다."""
    response = toolloop.respond(toolloop.Trace(), lat=None, lng=None)

    assert response.answer
    assert "도구" not in "".join(segment.text for segment in response.answer)


async def test_category_search_refuses_a_search_with_no_axis(ctx: ToolContext) -> None:
    """조건이 하나도 없으면 전국 20곳이 무작위로 나간다."""
    result = await CATALOG["category_search"].run(ctx, {})

    assert result.rows == []
    assert result.fact is not None and "알려주시면" in result.fact


async def test_a_category_outside_the_travel_pool_is_refused(ctx: ToolContext) -> None:
    """숙박·레포츠는 코드가 풀려도 여행지 풀이 빼므로 결과가 0곳이 된다."""
    assert not categories.in_travel_pool("AC010100")
    assert not categories.in_travel_pool("LS030100")
    assert not categories.in_travel_pool("SH010100")
    assert not categories.in_travel_pool("VE110100")
    assert categories.in_travel_pool("NA010100")
    assert categories.in_travel_pool("VE010100")


async def test_a_refused_search_stops_the_turn(ctx: ToolContext) -> None:
    """관찰로 부탁만 하면 모델이 지역만 남겨 다시 불러 엉뚱한 20곳이 나간다."""
    result = await CATALOG["category_search"].run(ctx, {})

    assert result.stop is True
