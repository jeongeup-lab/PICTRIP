from __future__ import annotations

from dataclasses import dataclass

import pytest
from fakeredis.aioredis import FakeRedis

from app.modules.agent.errors import AgentNoResults
from app.modules.agent.schemas import AskContext, AskContextSpot, AskResponse, QueryIntent
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import detail as detail_service
from app.modules.agent.services import intent as intent_service
from app.modules.spots.services.rows import SpotDetailRow, SpotIntroRow

SEBYEONGGWAN = AskContextSpot(contentId="126198", title="통영 세병관")


@dataclass
class SimpleTitleRow:
    title: str
    lat: float | None
    lng: float | None


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


async def _ask(question: str, *, intent: QueryIntent, row: SpotDetailRow | None, monkeypatch):
    async def fake_extract(q, *, prior=None, prior_spots=None):  # type: ignore[no-untyped-def]
        return intent

    async def fake_detail(session, kto, redis, content_id, *, defer_refresh=False):  # type: ignore[no-untyped-def]
        if row is None:
            raise AgentNoResults()
        return row

    monkeypatch.setattr(intent_service, "extract_intent", fake_extract)
    monkeypatch.setattr(detail_service, "load_spot_detail", fake_detail)
    return await ask_service.ask(
        _ExplodingSession(),  # type: ignore[arg-type]
        FakeRedis(),
        None,
        question=question,
        lat=None,
        lng=None,
        image_bytes=None,
        image_mime=None,
        context=AskContext(spots=[SEBYEONGGWAN]),
    )


def _text(answer: AskResponse) -> str:
    return "".join(segment.text for segment in answer.answer)


async def test_an_opening_hours_question_answers_instead_of_searching(monkeypatch) -> None:
    intent = QueryIntent(task="detail", targetPlace="통영 세병관", detailFields=["hours"])

    answer = await _ask(
        "세병관 영업시간 몇시야?",
        intent=intent,
        row=_detail(usetime="09:00~18:00"),
        monkeypatch=monkeypatch,
    )

    assert "09:00~18:00" in _text(answer)


async def test_a_detail_turn_names_the_spot_it_answered_about(monkeypatch) -> None:
    intent = QueryIntent(task="detail", targetPlace="통영 세병관", detailFields=["hours"])

    answer = await _ask(
        "세병관 영업시간 몇시야?",
        intent=intent,
        row=_detail(usetime="09:00~18:00"),
        monkeypatch=monkeypatch,
    )

    assert "통영 세병관" in _text(answer)
    assert [spot.contentId for spot in answer.spots] == ["126198"]


async def test_a_missing_field_is_admitted_not_invented(monkeypatch) -> None:
    intent = QueryIntent(task="detail", targetPlace="통영 세병관", detailFields=["parking"])

    answer = await _ask(
        "주차 되나?", intent=intent, row=_detail(usetime="09:00~18:00"), monkeypatch=monkeypatch
    )

    text = _text(answer)
    assert detail_service.UNKNOWN_HINT in text
    assert "09:00~18:00" not in text


async def test_a_detail_turn_records_the_lookup_step(monkeypatch) -> None:
    intent = QueryIntent(task="detail", targetPlace="통영 세병관", detailFields=["hours"])

    answer = await _ask(
        "몇시까지 해?", intent=intent, row=_detail(usetime="09:00~18:00"), monkeypatch=monkeypatch
    )

    assert [step.tool for step in answer.steps] == ["intent", "spot_detail"]


async def test_a_detail_question_about_nothing_we_can_pin_falls_back_to_search() -> None:
    intent = QueryIntent(task="detail", targetPlace="없는곳", regionHints=["통영"])

    assert ask_service.detail_target(intent, context=AskContext(spots=[SEBYEONGGWAN])) is None


async def test_a_detail_question_pins_the_focused_card_over_the_named_one() -> None:
    intent = QueryIntent(task="detail", targetPlace="통영 세병관")
    context = AskContext(spots=[SEBYEONGGWAN], focusContentId="999")

    assert ask_service.detail_target(intent, context=context) == "999"


async def test_an_unsupported_task_says_so_without_searching(monkeypatch) -> None:
    intent = QueryIntent(task="unsupported", regionHints=["통영"])

    answer = await _ask("통영 1박2일 일정 짜줘", intent=intent, row=None, monkeypatch=monkeypatch)

    assert answer.spots == []
    assert _text(answer) == ask_service.UNSUPPORTED_ANSWER


async def test_smalltalk_never_searches_even_with_a_region_in_it(monkeypatch) -> None:
    intent = QueryIntent(task="smalltalk", regionHints=["통영"])

    answer = await _ask("통영 좋지 그치?", intent=intent, row=None, monkeypatch=monkeypatch)

    assert answer.spots == []
    assert _text(answer) == ask_service.BLANK_ANSWER


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


def test_a_target_matches_a_title_that_carries_a_region_prefix() -> None:
    intent = QueryIntent(task="detail", targetPlace="세병관")

    assert ask_service.detail_target(intent, context=AskContext(spots=[SEBYEONGGWAN])) == "126198"


def test_a_target_that_matches_nothing_does_not_pin_the_wrong_card() -> None:
    other = AskContextSpot(contentId="1", title="해운대해수욕장")
    intent = QueryIntent(task="detail", targetPlace="세병관")

    assert ask_service.detail_target(intent, context=AskContext(spots=[SEBYEONGGWAN, other]))
    assert ask_service.detail_target(intent, context=AskContext(spots=[other])) is None


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


async def test_a_marked_up_value_reaches_the_sentence_clean(monkeypatch) -> None:
    intent = QueryIntent(task="detail", targetPlace="통영 세병관", detailFields=["parking"])

    answer = await _ask(
        "주차 되나?",
        intent=intent,
        row=_detail(parking="가능<br>요금(무료)"),
        monkeypatch=monkeypatch,
    )

    text = _text(answer)
    assert "<br>" not in text
    assert "가능 요금(무료)" in text


def test_food_codes_are_recognised_as_a_food_scope() -> None:
    from app.modules.agent.services import retrieve

    assert retrieve.food_action(["FD010100", "FD020100"]) == "food"
    assert retrieve.food_action(["FD050100"]) == "cafe"
    assert retrieve.food_action(["FD030100"]) == "cafe"
    assert retrieve.food_action(["VE060100"]) is None
    assert retrieve.food_action(["FD010100", "VE060100"]) is None
    assert retrieve.food_action([]) is None


async def test_a_food_search_with_no_origin_at_all_says_how_to_get_one(monkeypatch) -> None:
    from app.modules.agent.services import retrieve

    async def fake_scope(session, keywords):  # type: ignore[no-untyped-def]
        return retrieve.CategoryScope(codes=["FD010100"], matched=list(keywords))

    async def fake_region(session, *, hints):  # type: ignore[no-untyped-def]
        return retrieve.EMPTY_REGION_SCOPE

    monkeypatch.setattr(retrieve, "resolve_category_scope", fake_scope)
    monkeypatch.setattr(retrieve, "resolve_region_scope", fake_region)

    answer = await _ask(
        "맛집 아무데나",
        intent=QueryIntent(categoryKeywords=["맛집"]),
        row=None,
        monkeypatch=monkeypatch,
    )

    assert answer.spots == []
    assert _text(answer) == ask_service.FOOD_NEEDS_ORIGIN_ANSWER


async def test_a_question_that_wants_a_search_but_named_no_axis_asks_for_one(monkeypatch) -> None:
    answer = await _ask(
        "아이랑 갈 만한 곳", intent=QueryIntent(), row=None, monkeypatch=monkeypatch
    )

    assert _text(answer) == ask_service.NO_AXIS_ANSWER
    assert _text(answer) != ask_service.BLANK_ANSWER


async def test_pure_smalltalk_keeps_the_plain_greeting(monkeypatch) -> None:
    answer = await _ask(
        "안녕", intent=QueryIntent(task="smalltalk"), row=None, monkeypatch=monkeypatch
    )

    assert _text(answer) == ask_service.BLANK_ANSWER


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
    assert retrieve.taxonomy_word("야시장") == "시장"
    assert retrieve.taxonomy_word("박물관") == "박물관"


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


async def test_a_region_is_a_good_enough_origin_for_food(monkeypatch) -> None:
    from app.modules.agent.services import retrieve

    async def fake_scope(session, keywords):  # type: ignore[no-untyped-def]
        return retrieve.CategoryScope(codes=[], matched=[])

    async def fake_region(session, *, hints):  # type: ignore[no-untyped-def]
        return retrieve.RegionScope(
            prefixes=["전북특별자치도 정읍시"], sido_prefixes=["전북특별자치도"]
        )

    seen: dict[str, object] = {}

    async def fake_food(session, *, action, region_prefixes):  # type: ignore[no-untyped-def]
        seen["action"] = action
        seen["prefixes"] = region_prefixes
        return []

    monkeypatch.setattr(retrieve, "resolve_category_scope", fake_scope)
    monkeypatch.setattr(retrieve, "resolve_region_scope", fake_region)
    monkeypatch.setattr(retrieve, "search_food", fake_food)

    await _ask(
        "정읍 맛집",
        intent=QueryIntent(categoryKeywords=["맛집"], regionHints=["정읍"]),
        row=None,
        monkeypatch=monkeypatch,
    )

    assert seen["action"] == "food"
    assert seen["prefixes"] == ["전북특별자치도 정읍시"]


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
    found = await geocode.locate(None, None, "전주 한옥마을")  # type: ignore[arg-type]

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

    found = await geocode.locate(None, None, "대천역")  # type: ignore[arg-type]

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

    assert await geocode.locate(None, None, "한옥마을") is None  # type: ignore[arg-type]


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

    found = await geocode.locate(None, None, "대천역")  # type: ignore[arg-type]

    assert found is not None
    assert found.title == "대천역"
