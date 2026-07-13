from pictrip_data.overseas.backfill import (
    _filename,
    backfill_overseas_descriptions,
    backfill_overseas_thumbs,
)
from pictrip_data.overseas.commons import Credit
from pictrip_data.overseas.countries import Country
from pictrip_data.overseas.upsert import upsert_overseas
from pictrip_data.overseas.wikidata import RawSpot

JP = Country("Q17", "JP", "일본")
FR = Country("Q142", "FR", "프랑스")
SPOT = RawSpot("QTESTBF1", "교토", "Kyoto", "옛 수도", "Kyoto Temple.jpg", 90, 35.0, 135.7, JP)
NODESC = RawSpot("QTESTBF2", "파리", "Paris", None, "Paris.jpg", 120, 48.8, 2.3, FR)
DIRECT = "https://upload.wikimedia.org/wikipedia/commons/thumb/k/Kyoto.jpg/1200px-Kyoto.jpg"


class FakeWikipedia:
    def __init__(self, descriptions):
        self._descriptions = descriptions

    def fetch_descriptions(self, qids):
        return {q: self._descriptions[q] for q in qids if q in self._descriptions}


class FakeCommons:
    def __init__(self, thumb):
        self._thumb = thumb

    def fetch_credits(self, filenames):
        return {n: Credit(None, None, None, self._thumb) for n in filenames}


def test_filename_unquotes_and_strips_prefix():
    assert _filename("https://commons.wikimedia.org/wiki/File:A%20B.jpg") == "A B.jpg"
    assert _filename(None) is None
    assert _filename("https://example.com/x") is None


def test_backfill_rewrites_filepath_and_preserves_embedding(db_conn):
    with db_conn.cursor() as cur:
        upsert_overseas(cur, SPOT, Credit("A", "CC", None, None))
        cur.execute(
            "UPDATE overseas_spots SET embedding = array_fill(0.2::real, ARRAY[512])::halfvec "
            "WHERE wikidata_id = 'QTESTBF1'"
        )
    db_conn.commit()
    with db_conn.cursor() as cur:
        cur.execute("SELECT image_url FROM overseas_spots WHERE wikidata_id = 'QTESTBF1'")
        assert "Special:FilePath" in cur.fetchone()[0]

    result = backfill_overseas_thumbs(commons=FakeCommons(DIRECT), conn=db_conn)

    assert result["updated"] == 1
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT image_url, embedding IS NULL FROM overseas_spots WHERE wikidata_id = 'QTESTBF1'"
        )
        assert cur.fetchone() == (DIRECT, False)


def test_backfill_skips_when_thumb_missing(db_conn):
    with db_conn.cursor() as cur:
        upsert_overseas(cur, SPOT, Credit("A", "CC", None, None))
    db_conn.commit()

    result = backfill_overseas_thumbs(commons=FakeCommons(None), conn=db_conn)

    assert result["skipped"] == 1
    assert result["updated"] == 0
    with db_conn.cursor() as cur:
        cur.execute("SELECT image_url FROM overseas_spots WHERE wikidata_id = 'QTESTBF1'")
        assert "Special:FilePath" in cur.fetchone()[0]


def test_backfill_descriptions_fills_only_empty_rows(db_conn):
    with db_conn.cursor() as cur:
        upsert_overseas(cur, SPOT, Credit("A", "CC", None, None))
        upsert_overseas(cur, NODESC, Credit("A", "CC", None, None))
    db_conn.commit()

    result = backfill_overseas_descriptions(
        wikipedia=FakeWikipedia({"QTESTBF2": "파리는 프랑스의 수도이다."}), conn=db_conn
    )

    assert result == {"scanned": 1, "updated": 1, "skipped": 0}
    with db_conn.cursor() as cur:
        cur.execute("SELECT description_ko FROM overseas_spots WHERE wikidata_id = 'QTESTBF2'")
        assert cur.fetchone()[0] == "파리는 프랑스의 수도이다."
        cur.execute("SELECT description_ko FROM overseas_spots WHERE wikidata_id = 'QTESTBF1'")
        assert cur.fetchone()[0] == "옛 수도"


def test_backfill_descriptions_skips_when_no_extract(db_conn):
    with db_conn.cursor() as cur:
        upsert_overseas(cur, NODESC, Credit("A", "CC", None, None))
    db_conn.commit()

    result = backfill_overseas_descriptions(wikipedia=FakeWikipedia({}), conn=db_conn)

    assert result == {"scanned": 1, "updated": 0, "skipped": 1}
    with db_conn.cursor() as cur:
        cur.execute("SELECT description_ko FROM overseas_spots WHERE wikidata_id = 'QTESTBF2'")
        assert cur.fetchone()[0] is None
