from app.modules.agent.services.blurb import MAX_BLURB_CHARS, excerpt


def test_an_empty_overview_yields_nothing() -> None:
    assert excerpt(None) is None
    assert excerpt("") is None
    assert excerpt("   ") is None


def test_a_short_overview_is_handed_over_unchanged() -> None:
    assert excerpt("우도 동쪽의 백사장이다.") == "우도 동쪽의 백사장이다."


def test_only_the_first_sentence_survives() -> None:
    overview = "우도 동쪽의 백사장이다. 여름에는 해수욕장으로 개장한다."

    assert excerpt(overview) == "우도 동쪽의 백사장이다."


def test_a_long_first_sentence_is_cut_with_an_ellipsis() -> None:
    overview = "가" * 200

    result = excerpt(overview)

    assert result is not None
    assert result.endswith("…")
    assert len(result) == MAX_BLURB_CHARS + 1


def test_the_kept_text_is_a_verbatim_prefix_never_a_rewrite() -> None:
    overview = "제주 동쪽 해안을 따라 이어지는 백사장으로, 물빛이 밝고 수심이 얕아 아이들과 함께 걷기 좋다."

    result = excerpt(overview)

    assert result is not None
    assert overview.startswith(result.rstrip("…"))


def test_markup_and_stray_whitespace_are_flattened() -> None:
    assert excerpt("<b>우도</b>\n\n  동쪽의   백사장이다.") == "우도 동쪽의 백사장이다."
