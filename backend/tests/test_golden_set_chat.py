from __future__ import annotations

import json
from typing import Any

import pytest

from scripts.travel_golden_set import (
    Case,
    ChatTranscript,
    formal_endings,
    judge_chat,
    transcript_of,
)


def sse(name: str, payload: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def spot(content_id: str, title: str, region: str = "제주특별자치도 제주시") -> dict[str, Any]:
    return {"contentId": content_id, "title": title, "regionLabel": region}


def transcript(
    *,
    answer: str,
    spots: list[dict[str, Any]] | None = None,
    deltas: list[str] | None = None,
) -> ChatTranscript:
    found = spots if spots is not None else []
    stream = "".join(sse("delta", {"text": piece}) for piece in (deltas or [answer]))
    if found:
        stream += sse("cards", {"spots": found, "tagBasis": None})
    stream += sse(
        "done",
        {
            "answerText": answer,
            "spots": found,
            "sources": [],
            "intent": {},
            "totalCount": len(found),
        },
    )
    return transcript_of(stream)


def chat_case(**kw: Any) -> Case:
    kw.setdefault("cid", "P0")
    kw.setdefault("group", "P 채팅")
    kw.setdefault("label", "test")
    kw.setdefault("payload", {"message": "제주 박물관"})
    kw.setdefault("chat", True)
    return Case(**kw)


def test_a_well_formed_stream_folds_into_deltas_cards_and_done() -> None:
    parsed = transcript(
        answer="제주 박물관을 찾았어요.",
        spots=[spot("1", "국립제주박물관")],
        deltas=["제주 ", "박물관을 ", "찾았어요."],
    )

    assert parsed.streamed == "제주 박물관을 찾았어요."
    assert parsed.done is not None
    assert parsed.done["answerText"] == "제주 박물관을 찾았어요."
    assert len(parsed.cards) == 1
    assert parsed.error is None


def test_an_error_event_is_captured_instead_of_a_done_event() -> None:
    parsed = transcript_of(sse("error", {"code": "AGENT_NO_RESULTS", "message": "없어요"}))

    assert parsed.error is not None
    assert parsed.error["code"] == "AGENT_NO_RESULTS"
    assert parsed.done is None


def test_a_clean_answer_grounded_in_the_cards_passes() -> None:
    result = judge_chat(
        chat_case(expect_spots="some"),
        200,
        transcript(
            answer="**국립제주박물관**을 추천해요.",
            spots=[spot("1", "국립제주박물관")],
        ),
    )

    assert result.ok is True, result.reasons


def test_a_bold_place_name_absent_from_the_cards_is_reported_as_hallucination() -> None:
    result = judge_chat(
        chat_case(),
        200,
        transcript(
            answer="**성산일출봉**이 좋아요.",
            spots=[spot("1", "국립제주박물관")],
        ),
    )

    assert result.ok is False
    assert any("성산일출봉" in reason for reason in result.reasons)


def test_a_bold_span_taken_from_the_question_is_not_a_hallucination() -> None:
    result = judge_chat(
        chat_case(payload={"message": "제주 박물관"}),
        200,
        transcript(answer="**제주** 쪽으로 찾아볼게요.", spots=[]),
    )

    assert result.ok is True, result.reasons


def test_a_leaked_cards_marker_fails_even_when_the_prose_reads_fine() -> None:
    result = judge_chat(
        chat_case(),
        200,
        transcript(
            answer="추천이에요.\n[[cards]]\n- **국립제주박물관**",
            spots=[spot("1", "국립제주박물관")],
        ),
    )

    assert result.ok is False
    assert any("marker" in reason for reason in result.reasons)


def test_a_formal_sentence_ending_fails_the_style_rule() -> None:
    result = judge_chat(
        chat_case(),
        200,
        transcript(answer="제주 박물관을 추천합니다.", spots=[spot("1", "국립제주박물관")]),
    )

    assert result.ok is False
    assert any("합쇼체" in reason for reason in result.reasons)


def test_a_phone_number_fails_because_the_writer_has_no_such_ground_truth() -> None:
    result = judge_chat(
        chat_case(),
        200,
        transcript(answer="문의는 064-720-8000 이에요.", spots=[spot("1", "국립제주박물관")]),
    )

    assert result.ok is False
    assert any("전화" in reason for reason in result.reasons)


def test_a_stream_that_disagrees_with_the_final_answer_text_fails() -> None:
    stream = sse("delta", {"text": "제주 박물관"}) + sse(
        "done", {"answerText": "전혀 다른 답", "spots": [], "totalCount": 0}
    )

    result = judge_chat(chat_case(), 200, transcript_of(stream))

    assert result.ok is False
    assert any("stream" in reason for reason in result.reasons)


def test_a_stream_that_never_finishes_fails_rather_than_passing_silently() -> None:
    result = judge_chat(chat_case(), 200, transcript_of(sse("delta", {"text": "제주"})))

    assert result.ok is False
    assert any("done" in reason for reason in result.reasons)


def test_an_empty_answer_fails() -> None:
    result = judge_chat(chat_case(), 200, transcript(answer="   ", spots=[]))

    assert result.ok is False
    assert any("empty" in reason for reason in result.reasons)


def test_an_expected_error_code_still_matches_over_the_chat_stream() -> None:
    result = judge_chat(
        chat_case(expect_error="AGENT_NO_RESULTS"),
        200,
        transcript_of(sse("error", {"code": "AGENT_NO_RESULTS", "message": "없어요"})),
    )

    assert result.ok is True, result.reasons


@pytest.mark.parametrize("sentence", ["추천합니다", "좋습니다", "여기입니다", "됩니다"])
def test_a_bieup_final_before_nida_is_read_as_formal_speech(sentence: str) -> None:
    assert formal_endings(sentence)


@pytest.mark.parametrize("sentence", ["그건 아니다", "지금은 한가하니다행이에요"])
def test_a_syllable_without_a_bieup_final_is_not_formal_speech(sentence: str) -> None:
    assert formal_endings(sentence) == []


def test_a_spot_expectation_of_none_still_applies_over_the_chat_stream() -> None:
    result = judge_chat(
        chat_case(expect_spots="none"),
        200,
        transcript(answer="안녕하세요, 어디로 갈까요?", spots=[spot("1", "국립제주박물관")]),
    )

    assert result.ok is False


def test_a_citation_matching_a_card_passes() -> None:
    result = judge_chat(
        chat_case(expect_spots="some"),
        200,
        transcript(answer="**국립제주박물관**[1]이 좋아요.", spots=[spot("1", "국립제주박물관")]),
    )

    assert result.ok is True, result.reasons


def test_a_citation_past_the_last_card_is_caught() -> None:
    result = judge_chat(
        chat_case(),
        200,
        transcript(answer="**국립제주박물관**[7]이 좋아요.", spots=[spot("1", "국립제주박물관")]),
    )

    assert result.ok is False
    assert any("[7]" in reason for reason in result.reasons)


def test_a_citation_when_no_cards_came_back_is_caught() -> None:
    result = judge_chat(
        chat_case(expect_spots="none"),
        200,
        transcript(answer="거기[1] 좋아요.", spots=[]),
    )

    assert result.ok is False
