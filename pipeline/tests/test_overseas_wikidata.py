import json
from pathlib import Path

from pictrip_data.overseas.countries import COUNTRIES, Country
from pictrip_data.overseas.wikidata import RawSpot, parse_bindings

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


def test_countries_shape():
    assert len(COUNTRIES) >= 25
    assert all(len(c.code) == 2 for c in COUNTRIES)
