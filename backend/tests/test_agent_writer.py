from __future__ import annotations

import json

from app.modules.agent.schemas import AgentSpotCard, QueryIntent
from app.modules.agent.services import writer


def card(content_id: str, title: str) -> AgentSpotCard:
    return AgentSpotCard(contentId=content_id, title=title, regionLabel="제주 제주시")


def _prompt(*titles: str) -> tuple[str, str]:
    return writer.build_prompt(
        question="제주 박물관",
        intent=QueryIntent(regionHints=["제주"]),
        spots=[card(str(index), title) for index, title in enumerate(titles, start=1)],
        blog_posts=[],
        client_time=None,
        history=[],
    )


def test_the_hallucination_rule_sits_at_the_very_end_where_models_actually_follow_it() -> None:
    _system, user_text = _prompt("국립제주박물관")

    assert user_text.endswith(writer.REMINDER)
    body_end = user_text.index(writer.REMINDER)
    assert user_text.index("spots 목록에 없는 장소 이름을 절대") > body_end
    assert "국립제주박물관" in user_text[:body_end]


def test_every_spot_carries_the_number_the_answer_must_cite() -> None:
    _system, user_text = _prompt("국립제주박물관", "성산일출봉", "만장굴")

    payload = json.loads(user_text[: user_text.index("\n\n" + writer.REMINDER)])

    assert [spot["n"] for spot in payload["spots"]] == [1, 2, 3]
    assert payload["spots"][1]["title"] == "성산일출봉"


def test_the_writer_is_told_to_cite_by_number() -> None:
    system, _user_text = _prompt("국립제주박물관")

    assert "[1]" in system
    assert "번호" in system


def test_the_cards_marker_is_gone_so_no_parser_has_to_defend_against_it() -> None:
    system, user_text = _prompt("국립제주박물관")

    assert "cards" not in system
    assert "cards" not in user_text


def test_the_stream_is_passed_through_untouched_so_deltas_match_the_final_text() -> None:
    """번호 범위 검사는 클라이언트가 한다.

    서버가 스트리밍 중 `[7]` 을 잘라내려면 조각 걸친 토큰을 버퍼링해야 하고,
    최종 텍스트만 고치면 delta 와 done.answerText 가 어긋난다.
    """
    assert not hasattr(writer, "parse_stream")
    assert not hasattr(writer, "WriterCards")
