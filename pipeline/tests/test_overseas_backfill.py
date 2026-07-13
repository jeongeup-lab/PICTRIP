from pictrip_data.overseas.backfill import _filename, backfill_overseas_thumbs
from pictrip_data.overseas.commons import Credit
from pictrip_data.overseas.countries import Country
from pictrip_data.overseas.upsert import upsert_overseas
from pictrip_data.overseas.wikidata import RawSpot

JP = Country("Q17", "JP", "일본")
SPOT = RawSpot("QBF1", "교토", "Kyoto", "옛 수도", "Kyoto Temple.jpg", 90, 35.0, 135.7, JP)
DIRECT = "https://upload.wikimedia.org/wikipedia/commons/thumb/k/Kyoto.jpg/1200px-Kyoto.jpg"


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
            "WHERE wikidata_id = 'QBF1'"
        )
    db_conn.commit()
    with db_conn.cursor() as cur:
        cur.execute("SELECT image_url FROM overseas_spots WHERE wikidata_id = 'QBF1'")
        assert "Special:FilePath" in cur.fetchone()[0]

    result = backfill_overseas_thumbs(commons=FakeCommons(DIRECT), conn=db_conn)

    assert result["updated"] == 1
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT image_url, embedding IS NULL FROM overseas_spots WHERE wikidata_id = 'QBF1'"
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
        cur.execute("SELECT image_url FROM overseas_spots WHERE wikidata_id = 'QBF1'")
        assert "Special:FilePath" in cur.fetchone()[0]
