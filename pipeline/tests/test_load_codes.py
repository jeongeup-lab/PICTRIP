import httpx

from pictrip_data.kto.client import KtoClient
from pictrip_data.master.load_codes import load_codes

# Live-verified ldongCode2 shape: region repeats per sigungu.
LDONG_ROWS = [
    {
        "lDongRegnCd": "11",
        "lDongRegnNm": "서울특별시",
        "lDongSignguCd": "110",
        "lDongSignguNm": "종로구",
        "rnum": 1,
    },
    {
        "lDongRegnCd": "11",
        "lDongRegnNm": "서울특별시",
        "lDongSignguCd": "140",
        "lDongSignguNm": "중구",
        "rnum": 2,
    },
    {
        "lDongRegnCd": "26",
        "lDongRegnNm": "부산광역시",
        "lDongSignguCd": "110",
        "lDongSignguNm": "중구",
        "rnum": 3,
    },
    {
        # Sejong: KTO gives the province as 5-char '36110' (not 2-char).
        "lDongRegnCd": "36110",
        "lDongRegnNm": "세종특별자치시",
        "lDongSignguCd": "36110",
        "lDongSignguNm": "세종특별자치시",
        "rnum": 4,
    },
]

LCLS_ROWS = [
    {
        "lclsSystm1Cd": "AC",
        "lclsSystm1Nm": "숙박",
        "lclsSystm2Cd": "AC01",
        "lclsSystm2Nm": "호텔",
        "lclsSystm3Cd": "AC010100",
        "lclsSystm3Nm": "호텔",
        "rnum": 1,
    },
    {
        "lclsSystm1Cd": "AC",
        "lclsSystm1Nm": "숙박",
        "lclsSystm2Cd": "AC02",
        "lclsSystm2Nm": "모텔",
        "lclsSystm3Cd": "AC020100",
        "lclsSystm3Nm": "모텔",
        "rnum": 2,
    },
]


class FakeClient:
    def __init__(self):
        self.calls = []

    def call(self, operation, **params):
        self.calls.append((operation, params))
        if operation == "ldongCode2":
            return LDONG_ROWS
        if operation == "lclsSystmCode2":
            return LCLS_ROWS
        raise AssertionError(f"unexpected operation {operation}")


def _cleanup_codes(conn):
    cur = conn.cursor()
    # Codes from this test's fixtures only.
    cur.execute("DELETE FROM sigungus WHERE ldong_regn_cd IN ('11','26','36')")
    cur.execute("DELETE FROM regions WHERE ldong_regn_cd IN ('11','26','36')")
    cur.execute("DELETE FROM lcls_systm_codes WHERE lcls_systm3_cd IN ('AC010100','AC020100')")
    conn.commit()


def test_load_codes_upserts_and_is_idempotent(db_conn):
    _cleanup_codes(db_conn)
    fake = FakeClient()
    try:
        load_codes(client=fake, conn=db_conn)

        cur = db_conn.cursor()
        # regions deduped (11 appears twice in the ldong list -> one row).
        cur.execute(
            "SELECT ldong_regn_cd, ldong_regn_nm FROM regions "
            "WHERE ldong_regn_cd IN ('11','26') ORDER BY ldong_regn_cd"
        )
        assert cur.fetchall() == [("11", "서울특별시"), ("26", "부산광역시")]

        # sigungus composite codes = regn + signgu.
        cur.execute(
            "SELECT ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm FROM sigungus "
            "WHERE ldong_regn_cd IN ('11','26') ORDER BY ldong_signgu_cd"
        )
        assert cur.fetchall() == [
            ("11110", "11", "종로구"),
            ("11140", "11", "중구"),
            ("26110", "26", "중구"),
        ]

        # lcls codes upserted with all columns.
        cur.execute(
            "SELECT lcls_systm3_cd, lcls_systm3_nm, lcls_systm2_cd, lcls_systm1_cd, "
            "lcls_systm2_nm, lcls_systm1_nm FROM lcls_systm_codes "
            "WHERE lcls_systm3_cd IN ('AC010100','AC020100') ORDER BY lcls_systm3_cd"
        )
        assert cur.fetchall() == [
            ("AC010100", "호텔", "AC01", "AC", "호텔", "숙박"),
            ("AC020100", "모텔", "AC02", "AC", "모텔", "숙박"),
        ]

        # Idempotent: second run, same counts, no error.
        load_codes(client=fake, conn=db_conn)
        cur.execute("SELECT count(*) FROM regions WHERE ldong_regn_cd IN ('11','26')")
        assert cur.fetchone()[0] == 2
        cur.execute("SELECT count(*) FROM sigungus WHERE ldong_regn_cd IN ('11','26')")
        assert cur.fetchone()[0] == 3
        cur.execute(
            "SELECT count(*) FROM lcls_systm_codes WHERE lcls_systm3_cd IN ('AC010100','AC020100')"
        )
        assert cur.fetchone()[0] == 2
    finally:
        _cleanup_codes(db_conn)


def test_client_call_unwraps_items():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("_type") == "json"
        assert request.url.params.get("lDongListYn") == "Y"
        body = {"response": {"body": {"items": {"item": LDONG_ROWS}}}}
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="http://test")
    client = KtoClient(client=http)
    rows = client.call("ldongCode2", lDongListYn="Y", numOfRows=400)
    assert rows == LDONG_ROWS


def test_client_call_empty_items_returns_list():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {"body": {"items": ""}}})

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="http://test")
    client = KtoClient(client=http)
    assert client.call("ldongCode2") == []


def test_client_call_single_item_wrapped_to_list():
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"response": {"body": {"items": {"item": LCLS_ROWS[0]}}}}
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="http://test")
    client = KtoClient(client=http)
    assert client.call("lclsSystmCode2") == [LCLS_ROWS[0]]


def test_load_codes_normalizes_sejong(db_conn):
    _cleanup_codes(db_conn)
    load_codes(client=FakeClient(), conn=db_conn)
    cur = db_conn.cursor()
    cur.execute("SELECT ldong_regn_nm FROM regions WHERE ldong_regn_cd = '36'")
    assert cur.fetchone() == ("세종특별자치시",)
    # composite = normalized regn '36' + signgu '36110' = '3636110' (fits varchar 8).
    cur.execute("SELECT ldong_regn_cd FROM sigungus WHERE ldong_signgu_cd = '3636110'")
    assert cur.fetchone() == ("36",)
    _cleanup_codes(db_conn)
