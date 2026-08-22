from __future__ import annotations

from dataclasses import dataclass

import pytest
from fakeredis.aioredis import FakeRedis

from app.modules.agent.repositories import CandidateRow
from app.modules.agent.schemas import (
    AskContextSpot,
    AskResponse,
    QueryIntent,
)
from app.modules.agent.services import anchor as anchor_service
from app.modules.agent.services import detail as detail_service
from app.modules.spots.services.rows import SpotDetailRow, SpotIntroRow

SEBYEONGGWAN = AskContextSpot(contentId="126198", title="통영 세병관")


@dataclass
class SimpleTitleRow:
    title: str
    lat: float | None
    lng: float | None
    content_id: str = "t1"
    addr1: str | None = None


def _coordless_row():  # type: ignore[no-untyped-def]

    return CandidateRow(
        content_id="126198",
        title="통영 세병관",
        addr1="경상남도 통영시 세병로 27",
        region_name="경상남도",
        sigungu_name="통영시",
        lat=None,
        lng=None,
        image_url=None,
        cpyrht_div_cd="Type1",
        concentration_rate=None,
    )


class _ExplodingSession:
    async def execute(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("a detail turn must not run a search")


def _detail(**intro: str | None) -> SpotDetailRow:
    return SpotDetailRow(
        content_id="126198",
        title="통영 세병관",
        first_image_url=None,
        addr1="경상남도 통영시 세병로 27",
        addr2=None,
        mapx=128.4,
        mapy=34.8,
        overview="세병관은 삼도수군통제영의 客舍이다.",
        homepage=None,
        tel=intro.pop("tel", None),
        region_name="경상남도",
        sigungu_name="통영시",
        detail_status="fresh",
        images=[],
        intro=SpotIntroRow(**intro),  # type: ignore[arg-type]
    )


def _text(answer: AskResponse) -> str:
    return "".join(segment.text for segment in answer.answer)


@pytest.mark.parametrize(
    "field,intro,expected",
    [
        ("hours", {"usetime": "09:00~18:00"}, "09:00~18:00"),
        ("closed", {"restdate": "월요일"}, "월요일"),
        ("parking", {"parking": "가능(30대)"}, "가능(30대)"),
        ("contact", {"infocenter": "055-650-0000"}, "055-650-0000"),
        ("fee", {"usefee": "어른 3,000원"}, "어른 3,000원"),
    ],
)
def test_each_field_reads_its_own_kto_column(field, intro, expected) -> None:
    row = SpotIntroRow(**intro)

    assert detail_service.field_value(row, None, field) == expected


@pytest.mark.parametrize(
    "noun,value,expected",
    [
        ("이용시간", "09:00~18:00", "이용시간은 09:00~18:00이에요."),
        ("문의", "055-645-3805", "문의는 055-645-3805예요."),
        ("주차", "가능", "주차는 가능이에요."),
        ("이용요금", "어른 2000원", "이용요금은 어른 2000원이에요."),
        ("쉬는 날", "월요일", "쉬는 날은 월요일이에요."),
    ],
)
def test_a_fact_sentence_picks_the_right_particles(noun, value, expected) -> None:
    assert detail_service.fact_sentence(noun, value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("가능", detail_service.PARKING_AVAILABLE),
        ("있음", detail_service.PARKING_AVAILABLE),
        ("불가능", detail_service.PARKING_UNAVAILABLE),
        ("없음", detail_service.PARKING_UNAVAILABLE),
        ("가능 요금 (무료)", None),
        ("가능 (소형 80대 / 대형 10대)", None),
    ],
)
def test_a_yes_no_parking_value_becomes_a_verb_not_a_noun(value, expected) -> None:
    assert detail_service.parking_sentence(value) == expected


@pytest.mark.parametrize(
    "fields,expected",
    [(["overview"], False), (["hours"], True), (["overview", "parking"], True), ([], True)],
)
async def test_intro_is_only_demanded_when_the_question_needs_it(
    fields, expected, monkeypatch
) -> None:
    seen: list[bool] = []

    async def fake_load(
        session, kto, redis, content_id, *, defer_refresh=False, require_intro=False
    ):  # type: ignore[no-untyped-def]
        seen.append(require_intro)
        return _detail(usetime="09:00~18:00")

    monkeypatch.setattr(detail_service, "load_spot_detail", fake_load)
    await detail_service.answer_about_spot(
        _ExplodingSession(),  # type: ignore[arg-type]
        FakeRedis(),
        None,
        content_id="126198",
        intent=QueryIntent(task="detail", detailFields=fields),
        steps=[],
    )

    assert seen == [expected]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("가능<br>요금(무료)", "가능 요금(무료)"),
        ("09:00~18:00<br/>동절기 17:00", "09:00~18:00 동절기 17:00"),
        ("주차 <b>가능</b>", "주차 가능"),
        ("&lt;주의&gt; 유료", "<주의> 유료"),
        ("평상시", "평상시"),
    ],
)
def test_a_fact_value_never_shows_markup(raw, expected) -> None:
    assert detail_service.plain(raw) == expected


def test_food_codes_are_recognised_as_a_food_scope() -> None:
    from app.modules.agent.services import retrieve

    assert retrieve.food_action(["FD010100", "FD020100"]) == "food"
    assert retrieve.food_action(["FD050100"]) == "cafe"
    assert retrieve.food_action(["FD030100"]) == "cafe"
    assert retrieve.food_action(["VE060100"]) is None
    assert retrieve.food_action(["FD010100", "VE060100"]) is None
    assert retrieve.food_action([]) is None


def test_everyday_food_words_route_even_when_the_taxonomy_has_no_such_name() -> None:
    from app.modules.agent.services import retrieve

    assert retrieve.food_word(["맛집"]) == "food"
    assert retrieve.food_word(["먹을 곳"]) == "food"
    assert retrieve.food_word(["카페"]) == "cafe"
    assert retrieve.food_word(["커피숍"]) == "cafe"
    assert retrieve.food_word(["박물관"]) is None
    assert retrieve.food_word(["맛집", "박물관"]) is None
    assert retrieve.food_word([]) is None


def test_everyday_nouns_map_onto_the_taxonomy_words() -> None:
    from app.modules.agent.services import retrieve

    assert retrieve.taxonomy_word("사찰") == "불교"
    assert retrieve.taxonomy_word("절") == "불교"
    assert retrieve.taxonomy_word("성당") == "기독교"
    assert retrieve.taxonomy_word("놀이공원") == "테마파크"
    assert retrieve.taxonomy_word("식물원") == "수목원"
    assert retrieve.taxonomy_word("박물관") == "박물관"


def test_a_shopping_word_stays_a_title_keyword_instead_of_a_dead_category() -> None:
    from app.modules.agent.services import retrieve

    assert retrieve.taxonomy_word("야시장") == "야시장"


async def test_a_synonym_search_keeps_the_user_word_in_the_answer() -> None:
    from app.modules.agent import repositories
    from app.modules.agent.services import retrieve

    asked: list[str] = []

    class _Session:
        async def execute(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("unused")

    async def fake_codes(session, keyword, *, limit=40):  # type: ignore[no-untyped-def]
        asked.append(keyword)
        return ["HS030100"] if keyword == "불교" else []

    original = repositories.find_category_codes
    repositories.find_category_codes = fake_codes  # type: ignore[assignment]
    try:
        scope = await retrieve.resolve_category_scope(_Session(), ["사찰"])  # type: ignore[arg-type]
    finally:
        repositories.find_category_codes = original  # type: ignore[assignment]

    assert asked == ["불교"]
    assert scope.codes == ["HS030100"]
    assert scope.matched == ["사찰"]


def test_a_food_pool_sql_is_available_per_category() -> None:
    from app.modules.spots.services import NearbyCategory, category_sql

    food = category_sql(NearbyCategory.food)
    cafe = category_sql(NearbyCategory.cafe)

    assert "FD01" in food and "FD05" not in food
    assert "FD05" in cafe


def test_a_geocode_hit_must_actually_carry_the_asked_name() -> None:
    from app.modules.agent.services import geocode

    assert geocode.names_match("대천역", "대천역 장항선") is True
    assert geocode.names_match("대천역", "대천천") is False
    assert geocode.names_match("한옥마을", "북촌도담") is False
    assert geocode.names_match("전주 한옥마을", "전북 전주 한옥마을 [슬로시티]") is True
    assert geocode.names_match("정읍역", "정읍역 (고속철도)") is True
    assert geocode.names_match("", "아무거나") is False


async def test_geocoding_prefers_a_kto_spot_that_carries_the_name(monkeypatch) -> None:
    from app.modules.agent.services import geocode

    async def fake_titles(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        return [
            SimpleTitleRow("전북 전주 한옥마을 [슬로시티]", 35.818, 127.153),
        ]

    monkeypatch.setattr(geocode, "search_spots_by_title", fake_titles)
    found = await geocode.locate(None, "전주 한옥마을")  # type: ignore[arg-type]

    assert found is not None
    assert found.title == "전북 전주 한옥마을 [슬로시티]"
    assert round(found.lat, 2) == 35.82


async def test_geocoding_falls_through_to_naver_when_no_spot_carries_the_name(
    monkeypatch,
) -> None:
    from app.modules.agent import naver
    from app.modules.agent.services import geocode

    async def fake_titles(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        return [SimpleTitleRow("대천천", 35.242, 129.019)]

    async def fake_local(client, query, *, display=3):  # type: ignore[no-untyped-def]
        return [naver.NaverPlace("대천역 장항선", None, "충청남도 보령시", 36.3416, 126.5867)]

    monkeypatch.setattr(geocode, "search_spots_by_title", fake_titles)
    monkeypatch.setattr(geocode, "naver_search", fake_local)
    monkeypatch.setattr(naver, "is_configured", lambda: True)

    found = await geocode.locate(None, "대천역")  # type: ignore[arg-type]

    assert found is not None
    assert round(found.lat, 2) == 36.34


async def test_geocoding_gives_up_rather_than_guessing(monkeypatch) -> None:
    from app.modules.agent import naver
    from app.modules.agent.services import geocode

    async def fake_titles(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        return []

    async def fake_local(client, query, *, display=3):  # type: ignore[no-untyped-def]
        return [naver.NaverPlace("북촌도담", None, "서울특별시 종로구", 37.577, 126.985)]

    monkeypatch.setattr(geocode, "search_spots_by_title", fake_titles)
    monkeypatch.setattr(geocode, "naver_search", fake_local)
    monkeypatch.setattr(naver, "is_configured", lambda: True)

    assert await geocode.locate(None, "한옥마을") is None  # type: ignore[arg-type]


async def test_the_origin_is_named_the_way_the_user_said_it(monkeypatch) -> None:
    from app.modules.agent import naver
    from app.modules.agent.services import geocode

    async def fake_titles(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        return []

    async def fake_local(client, query, *, display=3):  # type: ignore[no-untyped-def]
        return [naver.NaverPlace("타이어뱅크 대천역점", None, "충청남도 보령시", 36.34, 126.58)]

    monkeypatch.setattr(geocode, "search_spots_by_title", fake_titles)
    monkeypatch.setattr(geocode, "naver_search", fake_local)
    monkeypatch.setattr(naver, "is_configured", lambda: True)

    found = await geocode.locate(None, "대천역")  # type: ignore[arg-type]

    assert found is not None
    assert found.title == "대천역"


async def test_geocoding_narrows_the_spot_search_with_the_region_hint(monkeypatch) -> None:
    from app.modules.agent.services import geocode

    seen: dict[str, object] = {}

    async def fake_titles(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        seen["hint"] = region_hint
        return [
            SimpleTitleRow(
                "전북 전주 한옥마을 [슬로시티]",
                35.818,
                127.153,
                addr1="전북특별자치도 전주시 완산구 1",
            )
        ]

    monkeypatch.setattr(geocode, "search_spots_by_title", fake_titles)
    found = await geocode.locate(None, "한옥마을", region_hint="전주")  # type: ignore[arg-type]

    assert seen["hint"] == "전주"
    assert found is not None and round(found.lat, 2) == 35.82


async def test_geocoding_asks_naver_within_the_region(monkeypatch) -> None:
    from app.modules.agent import naver
    from app.modules.agent.services import geocode

    asked: dict[str, object] = {}

    async def fake_titles(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        return []

    async def fake_local(client, query, *, display=3):  # type: ignore[no-untyped-def]
        asked["query"] = query
        return [naver.NaverPlace("전주 한옥마을", None, "전북특별자치도 전주시", 35.818, 127.153)]

    monkeypatch.setattr(geocode, "search_spots_by_title", fake_titles)
    monkeypatch.setattr(geocode, "naver_search", fake_local)
    monkeypatch.setattr(naver, "is_configured", lambda: True)

    found = await geocode.locate(None, "한옥마을", region_hint="전주")  # type: ignore[arg-type]

    assert asked["query"] == "전주 한옥마을"
    assert found is not None


async def test_a_hit_outside_the_named_region_is_rejected(monkeypatch) -> None:
    from app.modules.agent import naver
    from app.modules.agent.services import geocode

    async def fake_titles(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        return []

    async def fake_local(client, query, *, display=3):  # type: ignore[no-untyped-def]
        return [naver.NaverPlace("송도 한옥마을", None, "인천광역시 연수구", 37.38, 126.65)]

    monkeypatch.setattr(geocode, "search_spots_by_title", fake_titles)
    monkeypatch.setattr(geocode, "naver_search", fake_local)
    monkeypatch.setattr(naver, "is_configured", lambda: True)

    assert await geocode.locate(None, "한옥마을", region_hint="전주") is None  # type: ignore[arg-type]


def test_an_empty_surrounding_keeps_the_asked_conditions() -> None:
    intent = QueryIntent(categoryKeywords=["맛집"], regionHints=["보령"])

    answer = anchor_service.empty_anchor_response("대천역", "food", prior_steps=[], intent=intent)

    assert answer.intent.categoryKeywords == ["맛집"]
    assert answer.intent.regionHints == ["보령"]


async def test_an_old_province_name_still_reaches_the_landmark(monkeypatch) -> None:
    from app.modules.agent import naver
    from app.modules.agent.services import geocode

    seen: dict[str, object] = {}

    async def fake_titles(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        seen["hint"] = region_hint
        return []

    async def fake_local(client, query, *, display=3):  # type: ignore[no-untyped-def]
        seen["query"] = query
        return [
            naver.NaverPlace("속초해수욕장", None, "강원특별자치도 속초시", 38.19, 128.60),
        ]

    monkeypatch.setattr(geocode, "search_spots_by_title", fake_titles)
    monkeypatch.setattr(geocode, "naver_search", fake_local)
    monkeypatch.setattr(naver, "is_configured", lambda: True)

    found = await geocode.locate(  # type: ignore[arg-type]
        None, "속초해수욕장", region_hint="강원도"
    )

    assert seen["hint"] == "강원"
    assert seen["query"] == "강원 속초해수욕장"
    assert found is not None and round(found.lat, 2) == 38.19


async def test_a_multi_word_region_hint_narrows_by_its_finest_token(monkeypatch) -> None:
    from app.modules.agent.services import geocode

    seen: dict[str, object] = {}

    async def fake_titles(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        seen["hint"] = region_hint
        return [
            SimpleTitleRow("속초해수욕장", 38.19, 128.60, addr1="강원특별자치도 속초시 조양동 1")
        ]

    monkeypatch.setattr(geocode, "search_spots_by_title", fake_titles)
    found = await geocode.locate(  # type: ignore[arg-type]
        None, "속초해수욕장", region_hint="강원도 속초"
    )

    assert seen["hint"] == "속초"
    assert found is not None


def test_an_empty_surrounding_drops_the_axes_it_never_applied() -> None:
    intent = QueryIntent(
        categoryKeywords=["맛집"],
        regionHints=["보령"],
        crowdPreference="quiet",
        indoorOnly=True,
        moodHints=["sea"],
    )

    answer = anchor_service.empty_anchor_response("대천역", "food", prior_steps=[], intent=intent)

    assert answer.intent.crowdPreference == "any"
    assert answer.intent.indoorOnly is False
    assert answer.intent.moodHints == []
    assert answer.intent.categoryKeywords == ["맛집"]


async def test_a_geocoded_origin_carries_the_id_that_excludes_it(monkeypatch) -> None:
    from app.modules.agent.services import geocode

    async def fake_titles(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        return [SimpleTitleRow("스타벅스 강남점", 37.50, 127.02, content_id="c1")]

    monkeypatch.setattr(geocode, "search_spots_by_title", fake_titles)
    found = await geocode.locate(None, "스타벅스 강남점")  # type: ignore[arg-type]

    assert found is not None and found.content_id == "c1"


async def test_a_same_name_place_in_another_province_is_rejected(monkeypatch) -> None:
    from app.modules.agent import naver
    from app.modules.agent.services import geocode

    seen: dict[str, object] = {}

    async def fake_titles(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        seen["hint"] = region_hint
        return [
            SimpleTitleRow(
                "고성탈박물관", 38.38, 128.46, addr1="강원특별자치도 고성군 1", content_id="w1"
            )
        ]

    monkeypatch.setattr(geocode, "search_spots_by_title", fake_titles)
    monkeypatch.setattr(naver, "is_configured", lambda: False)

    found = await geocode.locate(  # type: ignore[arg-type]
        None, "고성탈박물관", region_hint="경상남도 고성"
    )

    assert seen["hint"] == "고성"
    assert found is None


async def test_the_place_inside_the_named_province_is_still_taken(monkeypatch) -> None:
    from app.modules.agent.services import geocode

    async def fake_titles(session, query, *, region_hint=None, limit=3):  # type: ignore[no-untyped-def]
        return [
            SimpleTitleRow(
                "고성탈박물관", 35.02, 128.32, addr1="경상남도 고성군 1", content_id="s1"
            )
        ]

    monkeypatch.setattr(geocode, "search_spots_by_title", fake_titles)
    found = await geocode.locate(  # type: ignore[arg-type]
        None, "고성탈박물관", region_hint="경상남도 고성"
    )

    assert found is not None and found.content_id == "s1"
