from pictrip_data.overseas.wikipedia import (
    clean_extract,
    parse_extracts,
    parse_sitelinks,
)


def test_parse_sitelinks_keeps_only_kowiki_titles():
    payload = {
        "entities": {
            "Q1": {"sitelinks": {"kowiki": {"title": "파리"}, "enwiki": {"title": "Paris"}}},
            "Q2": {"sitelinks": {"enwiki": {"title": "London"}}},
            "Q3": {"sitelinks": {}},
        }
    }
    assert parse_sitelinks(payload) == {"Q1": "파리"}


def test_parse_extracts_returns_text_and_alias_maps():
    payload = {
        "query": {
            "normalized": [{"from": "파리_(도시)", "to": "파리 (도시)"}],
            "redirects": [{"from": "파리 (도시)", "to": "파리"}],
            "pages": {
                "10": {"title": "파리", "extract": "파리는 프랑스의 수도이다."},
                "11": {"title": "빈페이지"},
            },
        }
    }
    extracts, alias = parse_extracts(payload)
    assert extracts == {"파리": "파리는 프랑스의 수도이다."}
    assert alias == {"파리_(도시)": "파리 (도시)", "파리 (도시)": "파리"}


def test_clean_extract_takes_first_paragraph_and_collapses_space():
    text = "서울은  대한민국의 수도이다.\n\n두 번째 문단은 버린다."
    assert clean_extract(text) == "서울은 대한민국의 수도이다."


def test_clean_extract_truncates_at_sentence_boundary():
    body = "가나다라마바사아자차카타파하 " * 40
    result = clean_extract(body + "끝문장이다. 잘린다", max_chars=200)
    assert result is not None
    assert len(result) <= 202
    assert result.endswith("다.") or result.endswith("…")


def test_clean_extract_blank_returns_none():
    assert clean_extract("   \n  ") is None
