import json
from pathlib import Path

import httpx

from pictrip_data.overseas.countries import COUNTRIES, Country
from pictrip_data.overseas.wikidata import (
    RawSpot,
    WikidataClient,
    build_settlement_query,
    parse_bindings,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "sparql_bindings.json").read_text())
JP = Country(qid="Q17", code="JP", name_ko="일본")


def test_parse_bindings_full_row():
    spots = parse_bindings(FIXTURE, JP)
    s = spots[0]
    assert isinstance(s, RawSpot)
    assert s.wikidata_id.startswith("Q")
    assert s.name_ko and s.image_filename and s.fame_score > 0
    assert s.country.code == "JP"


def test_parse_bindings_optional_fields_absent():
    spots = parse_bindings(FIXTURE, JP)
    assert any(s.description_ko is None for s in spots)


def test_parse_bindings_dedupes_by_qid():
    doubled = FIXTURE + FIXTURE
    assert len(parse_bindings(doubled, JP)) == len(parse_bindings(FIXTURE, JP))


def test_build_settlement_query_shape():
    query = build_settlement_query(["Q85", "Q43332"])
    assert "VALUES ?item { wd:Q85 wd:Q43332 }" in query
    assert "wd:Q515" in query
    assert "?item wdt:P31 ?settlement ." in query
    assert "FILTER NOT EXISTS { ?item wdt:P31/wdt:P279* wd:Q839954 . }" in query


def _country_binding(qid: str) -> dict:
    return {
        "item": {"value": f"http://www.wikidata.org/entity/{qid}"},
        "ko": {"value": f"이름-{qid}"},
        "img": {"value": f"http://commons/{qid}.jpg"},
        "links": {"value": "42"},
    }


def test_fetch_country_drops_settlement_qids():
    def handler(request: httpx.Request) -> httpx.Response:
        if b"settlement" in request.content:
            bindings = [{"item": {"value": "http://www.wikidata.org/entity/Q85"}}]
        else:
            bindings = [_country_binding("Q85"), _country_binding("Q43332")]
        return httpx.Response(200, json={"results": {"bindings": bindings}})

    client = WikidataClient(httpx.Client(transport=httpx.MockTransport(handler)))
    spots = client.fetch_country(JP)
    assert [s.wikidata_id for s in spots] == ["Q43332"]


def test_countries_shape():
    assert len(COUNTRIES) >= 25
    assert all(len(c.code) == 2 for c in COUNTRIES)
