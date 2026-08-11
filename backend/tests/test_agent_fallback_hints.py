from __future__ import annotations

from app.modules.agent.schemas import QueryIntent
from app.modules.agent.services import intent as intent_service
from app.modules.agent.services import retrieve
from app.modules.spots.services import RegionPrefix

JEONGEUP = RegionPrefix(prefix="전북특별자치도 정읍시", sido="전북특별자치도")
BUSAN = RegionPrefix(prefix="부산광역시", sido="부산광역시")


def test_a_hint_the_region_table_knows_stays_a_region() -> None:
    kept, dropped = retrieve.split_unmappable_hints(["정읍"], {"정읍": JEONGEUP})
    assert kept == ["정읍"]
    assert dropped == []


def test_a_hint_the_region_table_does_not_know_is_not_a_region() -> None:
    kept, dropped = retrieve.split_unmappable_hints(["정읍", "삼겹살집"], {"정읍": JEONGEUP})
    assert kept == ["정읍"]
    assert dropped == ["삼겹살집"]


def test_a_multi_word_hint_survives_when_any_of_its_tokens_maps() -> None:
    kept, dropped = retrieve.split_unmappable_hints(["부산 해운대"], {"부산": BUSAN})
    assert kept == ["부산 해운대"]
    assert dropped == []


def test_every_hint_can_be_unmappable() -> None:
    kept, dropped = retrieve.split_unmappable_hints(["삼겹살집", "국밥"], {})
    assert kept == []
    assert dropped == ["삼겹살집", "국밥"]


def test_reclassifying_moves_the_unmappable_hint_into_the_category_axis() -> None:
    asked = QueryIntent(regionHints=["정읍", "삼겹살집"], categoryKeywords=[])
    fixed = retrieve.reclassified_intent(asked, kept=["정읍"], dropped=["삼겹살집"])
    assert fixed.regionHints == ["정읍"]
    assert fixed.categoryKeywords == ["삼겹살집"]


def test_reclassifying_does_not_duplicate_a_keyword_already_present() -> None:
    asked = QueryIntent(regionHints=["맛집"], categoryKeywords=["맛집"])
    fixed = retrieve.reclassified_intent(asked, kept=[], dropped=["맛집"])
    assert fixed.categoryKeywords == ["맛집"]


def test_reclassifying_keeps_the_other_axes_untouched() -> None:
    asked = QueryIntent(
        regionHints=["정읍", "삼겹살집"], moodHints=["sea"], crowdPreference="quiet", nearMe=True
    )
    fixed = retrieve.reclassified_intent(asked, kept=["정읍"], dropped=["삼겹살집"])
    assert fixed.moodHints == ["sea"]
    assert fixed.crowdPreference == "quiet"
    assert fixed.nearMe is True


def test_the_fallback_still_hands_the_whole_question_over_as_region_hints() -> None:
    guessed = intent_service.fallback_intent("정읍 삼겹살집")
    assert guessed.regionHints == ["정읍", "삼겹살집"]
