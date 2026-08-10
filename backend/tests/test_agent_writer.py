from __future__ import annotations

from collections.abc import AsyncIterator

from app.modules.agent.services import writer


async def _chunks(pieces: list[str]) -> AsyncIterator[str]:
    for piece in pieces:
        yield piece


async def _collect(pieces: list[str]) -> list[writer.WriterEvent]:
    return [event async for event in writer.parse_stream(_chunks(pieces))]


def _text(events: list[writer.WriterEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, writer.WriterDelta))


def _kinds(events: list[writer.WriterEvent]) -> list[str]:
    return [type(event).__name__ for event in events]


async def test_markers_are_consumed_and_never_leak_into_the_body() -> None:
    events = await _collect(
        [
            "부산 계곡이라면 여기예요.\n",
            "[[cards]]\n",
            "- **계곡-v1** 물이 맑아요.\n",
        ]
    )

    assert _kinds(events) == ["WriterDelta", "WriterCards", "WriterDelta"]
    assert _text(events) == "부산 계곡이라면 여기예요.\n- **계곡-v1** 물이 맑아요.\n"
    assert "[[" not in _text(events)


async def test_missing_cards_marker_falls_back_to_after_the_first_paragraph() -> None:
    events = await _collect(["결론 문장이에요.\n", "\n", "다음 문단이에요."])

    assert _kinds(events) == ["WriterDelta", "WriterDelta", "WriterCards", "WriterDelta"]


async def test_missing_markers_with_no_blank_line_put_cards_at_the_end() -> None:
    events = await _collect(["짧은 답이에요."])

    assert _kinds(events) == ["WriterDelta", "WriterCards"]
    assert _text(events) == "짧은 답이에요."


async def test_a_marker_split_across_chunk_boundaries_never_leaks() -> None:
    events = await _collect(
        [
            "첫 줄이에요.\n[",
            "[cards]",
            "]\n",
            "- **B** 팁이에요.\n[[sugg",
            "est: 하나 | 둘]]",
        ]
    )

    assert _text(events) == "첫 줄이에요.\n- **B** 팁이에요.\n"
    assert "[[" not in _text(events)
    assert _kinds(events) == ["WriterDelta", "WriterCards", "WriterDelta"]


async def test_an_unknown_bracket_line_is_dropped_without_leaking() -> None:
    events = await _collect(["본문이에요.\n", "[[unknown]]\n", "끝이에요."])

    assert "[[" not in _text(events)
    assert _text(events) == "본문이에요.\n끝이에요."
    assert _kinds(events).count("WriterCards") == 1


async def test_a_marker_after_flushed_prose_on_the_same_line_is_still_consumed() -> None:
    events = await _collect(["결론이에요. ", "[[cards]]\n남은 팁이에요."])

    assert "[[" not in _text(events)
    assert _kinds(events).count("WriterCards") == 1
    cards_at = _kinds(events).index("WriterCards")
    assert cards_at >= 1


async def test_the_cards_event_fires_at_most_once() -> None:
    events = await _collect(["결론이에요.\n", "\n", "[[cards]]\n", "팁이에요."])

    assert _kinds(events).count("WriterCards") == 1
    assert "[[" not in _text(events)
