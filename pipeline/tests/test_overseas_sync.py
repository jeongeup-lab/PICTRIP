from pictrip_data.overseas.commons import Credit
from pictrip_data.overseas.countries import Country
from pictrip_data.overseas.sync import sync_overseas
from pictrip_data.overseas.wikidata import RawSpot

JP = Country("Q17", "JP", "일본")
SPOT = RawSpot("QTEST1", "도쿄타워", "Tokyo Tower", "도쿄의 전파탑", "Tokyo Tower.jpg",
               120, 35.66, 139.75, JP)
CREDIT = Credit(author="Jane", license="CC BY-SA 4.0",
                license_url="https://creativecommons.org/licenses/by-sa/4.0")


class FakeWikidata:
    def fetch_country(self, country):
        return [SPOT] if country.code == "JP" else []


class FakeCommons:
    def fetch_credits(self, filenames):
        return {"Tokyo Tower.jpg": CREDIT}


def test_sync_overseas_inserts_and_records_run(db_conn):
    sync_overseas(wikidata=FakeWikidata(), commons=FakeCommons(), conn=db_conn,
                  countries=[JP])
    with db_conn.cursor() as cur:
        cur.execute("SELECT name_ko, image_url, image_source_url, fame_score "
                    "FROM overseas_spots WHERE wikidata_id = 'QTEST1'")
        row = cur.fetchone()
    assert row[0] == "도쿄타워"
    assert row[1].startswith("https://commons.wikimedia.org/wiki/Special:FilePath/")
    assert "width=800" in row[1]
    assert row[2].startswith("https://commons.wikimedia.org/wiki/File:")
    with db_conn.cursor() as cur:
        cur.execute("SELECT status, mode FROM sync_runs ORDER BY id DESC LIMIT 1")
        assert cur.fetchone() == ("success", "overseas")


def test_sync_overseas_upsert_preserves_hidden_and_resets_embedding_on_image_change(db_conn):
    sync_overseas(wikidata=FakeWikidata(), commons=FakeCommons(), conn=db_conn, countries=[JP])
    with db_conn.cursor() as cur:
        cur.execute("UPDATE overseas_spots SET is_hidden = true, "
                    "embedding = array_fill(0.1::real, ARRAY[512])::halfvec "
                    "WHERE wikidata_id = 'QTEST1'")
    db_conn.commit()
    changed = RawSpot("QTEST1", "도쿄타워", None, None, "New Tower.jpg", 130, None, None, JP)

    class Changed(FakeWikidata):
        def fetch_country(self, country):
            return [changed]

    class ChangedCommons(FakeCommons):
        def fetch_credits(self, filenames):
            return {"New Tower.jpg": CREDIT}

    sync_overseas(wikidata=Changed(), commons=ChangedCommons(), conn=db_conn, countries=[JP])
    with db_conn.cursor() as cur:
        cur.execute("SELECT is_hidden, embedding IS NULL FROM overseas_spots "
                    "WHERE wikidata_id = 'QTEST1'")
        assert cur.fetchone() == (True, True)
