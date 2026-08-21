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
