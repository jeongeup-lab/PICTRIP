from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo


from pictrip_data.kto.schemas import KtoSpot
from pictrip_data.sync.refcodes import load_ref_codes
from pictrip_data.sync.upsert import upsert_spots

KST = ZoneInfo("Asia/Seoul")


def _spot(**over):
    base = dict(
        content_id="T1",
        content_type_id=15,
        title="t",
        addr1=None,
        addr2=None,
        zipcode=None,
        mapx=Decimal("126.9"),
        mapy=Decimal("37.5"),
        ldong_regn_cd="11",
        ldong_signgu_cd="11110",
        lcls_systm1="EV",
        lcls_systm2="EV01",
        lcls_systm3="EV010600",
        cpyrht_div_cd="Type3",
        first_image_url="http://img",
        first_image2_url=None,
        show_flag=1,
        modified_time=datetime(2026, 6, 27, 4, 30, tzinfo=KST),
    )
    base.update(over)
    return KtoSpot(**base)


def _read(conn, cid):
    cur = conn.cursor()
    cur.execute(
        "SELECT show_flag, modified_time, ldong_signgu_cd FROM spots WHERE content_id=%s", (cid,)
    )
    return cur.fetchone()


def test_insert_then_idempotent_update(seed_refs):
    conn = seed_refs
    refs = load_ref_codes(conn)
    c = {"inserted": 0, "updated": 0, "soft_deleted": 0, "skipped": 0}
    upsert_spots(conn, [_spot()], refs, c)
    assert c["inserted"] == 1
    assert _read(conn, "T1")[0] == 1

    c2 = {"inserted": 0, "updated": 0, "soft_deleted": 0, "skipped": 0}
    newer = _spot(show_flag=0, modified_time=datetime(2026, 6, 28, 1, 0, tzinfo=KST))
    upsert_spots(conn, [newer], refs, c2)
    assert c2["soft_deleted"] == 1
    assert _read(conn, "T1")[0] == 0  # hidden


def test_newer_wins_guard_blocks_stale(seed_refs):
    conn = seed_refs
    refs = load_ref_codes(conn)
    upsert_spots(
        conn,
        [_spot(title="new", modified_time=datetime(2026, 6, 27, 4, 30, tzinfo=KST))],
        refs,
        {"inserted": 0, "updated": 0, "soft_deleted": 0, "skipped": 0},
    )
    # older modified_time must NOT overwrite
    upsert_spots(
        conn,
        [_spot(title="stale", modified_time=datetime(2020, 1, 1, tzinfo=KST))],
        refs,
        {"inserted": 0, "updated": 0, "soft_deleted": 0, "skipped": 0},
    )
    cur = conn.cursor()
    cur.execute("SELECT title FROM spots WHERE content_id='T1'")
    assert cur.fetchone()[0] == "new"


def test_unknown_fk_codes_nulled(seed_refs):
    conn = seed_refs
    refs = load_ref_codes(conn)
    spot = _spot(content_id="T2", ldong_signgu_cd="99999", lcls_systm3="ZZ999999")
    upsert_spots(conn, [spot], refs, {"inserted": 0, "updated": 0, "soft_deleted": 0, "skipped": 0})
    cur = conn.cursor()
    cur.execute("SELECT ldong_signgu_cd, lcls_systm3 FROM spots WHERE content_id='T2'")
    assert cur.fetchone() == (None, None)
