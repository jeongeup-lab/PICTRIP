from app.modules.feed.text import first_sentence


def test_first_sentence_korean_period():
    assert (
        first_sentence("산자락을 따라 늘어선 마을이다. 골목길이 이어진다.")
        == "산자락을 따라 늘어선 마을이다."
    )


def test_first_sentence_no_terminator_returns_whole():
    assert first_sentence("마침표 없는 소개문") == "마침표 없는 소개문"


def test_first_sentence_none_and_blank():
    assert first_sentence(None) is None
    assert first_sentence("   ") is None


def test_first_sentence_is_pure_truncation():
    src = "첫 문장이다. 둘째."
    out = first_sentence(src)
    assert out is not None and src.startswith(out)
