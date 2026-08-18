from __future__ import annotations

from typing import Any

import pytest

from app.modules.agent.services import scene as scene_service


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("가을 단풍 명소", "단풍"),
        ("단풍철에 갈만한 곳", "단풍"),
        ("낙엽 밟고 싶어", "단풍"),
        ("벚꽃 명소 알려줘", "벚꽃"),
        ("경주 벚꽃길", "벚꽃"),
        ("설경 보러 가고 싶어", "설경"),
        ("눈꽃 보러", "설경"),
        ("제주 유채꽃", "유채꽃"),
        ("핑크뮬리 사진 찍기 좋은 곳", "억새"),
        ("해돋이 명소", "일출"),
        ("석양 예쁜 곳", "일몰"),
        ("은하수 보이는 데", "은하수"),
        ("밤하늘 별 보러", "별"),
    ],
)
def test_a_season_or_phenomenon_is_recognised_as_a_scene(question: str, expected: str) -> None:
    assert scene_service.detect(question, []) == expected


@pytest.mark.parametrize("question", ["부산 바다", "경주 박물관", "한적한 카페", "안녕"])
def test_an_ordinary_question_is_not_mistaken_for_a_scene(question: str) -> None:
    assert scene_service.detect(question, []) is None


def test_a_scene_word_that_only_reached_the_keywords_still_counts() -> None:
    assert scene_service.detect("명소 추천", ["단풍"]) == "단풍"


async def test_the_prompt_vector_is_embedded_once_and_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_embed(prompts: list[str]) -> list[list[float]]:
        calls.append(prompts)
        return [[0.1] * 512]

    monkeypatch.setattr(scene_service.embedder, "embed_texts", fake_embed)
    scene_service._vectors.pop("벚꽃", None)

    first = await scene_service._vector("벚꽃")
    second = await scene_service._vector("벚꽃")

    assert first == second
    assert len(calls) == 1, "같은 장면을 두 번 임베딩하지 않는다"


async def test_a_scene_search_asks_the_vector_index_within_the_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def fake_match(
        _session: Any, vector: list[float], *, region_prefixes: list[str]
    ) -> list[Any]:
        seen["region_prefixes"] = region_prefixes
        seen["dims"] = len(vector)
        return []

    async def fake_briefs(_session: Any, ids: list[str]) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(scene_service.embedder, "embed_texts", lambda p: [[0.1] * 512])
    monkeypatch.setattr(scene_service.photo_service, "match_vector", fake_match)
    monkeypatch.setattr(scene_service.repositories, "load_candidates_by_ids", fake_briefs)
    scene_service._vectors.pop("단풍", None)

    found = await scene_service.search(None, "단풍", region_prefixes=["전북특별자치도 정읍시"])

    assert found == []
    assert seen["region_prefixes"] == ["전북특별자치도 정읍시"]
    assert seen["dims"] == 512
