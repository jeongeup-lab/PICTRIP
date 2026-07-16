from unittest.mock import patch

import httpx
from typer.testing import CliRunner

from pictrip_data.cli import app
from pictrip_data.sync.images import ALIVE, DEAD, UNKNOWN, mid_size_url, probe, validate_images

LIVE = "https://tong.visitkorea.or.kr/cms/resource/13/T13_image1_1.jpg"
DEAD_MID_ALIVE = "https://tong.visitkorea.or.kr/cms/resource/68/T68_image1_1.jpg"
DEAD_MID_ALIVE_MID = "https://tong.visitkorea.or.kr/cms/resource/68/T68_image2_1.jpg"
DEAD_MID_DEAD = "https://tong.visitkorea.or.kr/cms/resource/94/T94_image1_1.jpg"
DEAD_FOREIGN = "https://example.com/T_image1_1.jpg"
FLAKY = "https://tong.visitkorea.or.kr/cms/resource/50/T50_image1_1.jpg"
DEAD_MID_FLAKY = "https://tong.visitkorea.or.kr/cms/resource/77/T77_image1_1.jpg"

runner = CliRunner()


def _client(statuses: dict[str, int], content_type: str = "image/jpeg") -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        code = statuses.get(str(request.url))
        if code is None:
            raise httpx.ConnectError("unreachable", request=request)
        return httpx.Response(code, content=b"x", headers={"Content-Type": content_type})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_mid_size_url_rewrites_hires_marker():
    assert mid_size_url(DEAD_MID_ALIVE) == DEAD_MID_ALIVE_MID


def test_mid_size_url_rejects_foreign_host_and_missing_marker():
    assert mid_size_url(DEAD_FOREIGN) is None
    assert mid_size_url("https://tong.visitkorea.or.kr/cms/resource/1/T1_image3_1.jpg") is None


def test_probe_classification():
    client = _client({LIVE: 206, DEAD_MID_DEAD: 404, FLAKY: 500})
    assert probe(client, LIVE) == ALIVE
    assert probe(client, DEAD_MID_DEAD) == DEAD
    assert probe(client, FLAKY) == UNKNOWN
    assert probe(client, "https://tong.visitkorea.or.kr/timeout.jpg") == UNKNOWN


def test_probe_treats_non_image_200_as_unknown():
    client = _client({LIVE: 200}, content_type="text/html")
    assert probe(client, LIVE) == UNKNOWN


def test_probe_upgrades_http_to_https():
    client = _client({LIVE: 206})
    assert probe(client, LIVE.replace("https://", "http://")) == ALIVE


def _seed_spot(conn, content_id: str, url: str) -> None:
    conn.cursor().execute(
        "INSERT INTO spots (content_id, content_type_id, title, first_image_url) "
        "VALUES (%s, 12, 't', %s)",
        (content_id, url),
    )


def _image_url(conn, content_id: str) -> str | None:
    cur = conn.cursor()
    cur.execute("SELECT first_image_url FROM spots WHERE content_id = %s", (content_id,))
    return cur.fetchone()[0]


def test_validate_images_rewrites_clears_and_records(db_conn):
    for cid, url in [
        ("T1", LIVE),
        ("T2", DEAD_MID_ALIVE),
        ("T3", DEAD_MID_DEAD),
        ("T4", DEAD_FOREIGN),
        ("T5", FLAKY),
        ("T6", DEAD_MID_FLAKY),
    ]:
        _seed_spot(db_conn, cid, url)
    db_conn.commit()
    client = _client(
        {
            LIVE: 206,
            DEAD_MID_ALIVE: 404,
            DEAD_MID_ALIVE_MID: 200,
            DEAD_MID_DEAD: 404,
            DEAD_MID_DEAD.replace("_image1_1", "_image2_1"): 404,
            DEAD_FOREIGN: 404,
            FLAKY: 500,
            DEAD_MID_FLAKY: 404,
            DEAD_MID_FLAKY.replace("_image1_1", "_image2_1"): 500,
        }
    )

    result = validate_images(conn=db_conn, client=client)

    assert result == {"probed": 6, "rewritten": 1, "cleared": 2, "unknown": 2, "probes": 9}
    assert _image_url(db_conn, "T1") == LIVE
    assert _image_url(db_conn, "T2") == DEAD_MID_ALIVE_MID
    assert _image_url(db_conn, "T3") is None
    assert _image_url(db_conn, "T4") is None
    assert _image_url(db_conn, "T5") == FLAKY
    assert _image_url(db_conn, "T6") == DEAD_MID_FLAKY
    cur = db_conn.cursor()
    cur.execute("SELECT status, mode, fetched, updated, soft_deleted, skipped FROM sync_runs")
    assert cur.fetchall() == [("success", "validate-images", 6, 1, 2, 2)]


def test_validate_images_dry_run_writes_nothing(db_conn):
    _seed_spot(db_conn, "T2", DEAD_MID_ALIVE)
    db_conn.commit()
    client = _client({DEAD_MID_ALIVE: 404, DEAD_MID_ALIVE_MID: 200})

    result = validate_images(conn=db_conn, client=client, dry_run=True)

    assert result == {"probed": 1, "rewritten": 1, "cleared": 0, "unknown": 0, "probes": 2}
    assert _image_url(db_conn, "T2") == DEAD_MID_ALIVE
    cur = db_conn.cursor()
    cur.execute("SELECT count(*) FROM sync_runs")
    assert cur.fetchone()[0] == 0


def test_validate_images_limit_caps_probed_rows(db_conn):
    _seed_spot(db_conn, "T1", LIVE)
    _seed_spot(db_conn, "T2", DEAD_MID_ALIVE)
    db_conn.commit()
    client = _client({LIVE: 206})

    result = validate_images(conn=db_conn, client=client, limit=1)

    assert result["probed"] == 1
    assert _image_url(db_conn, "T2") == DEAD_MID_ALIVE


def test_validate_images_command_invokes():
    with patch("pictrip_data.cli.validate_images") as m:
        m.return_value = {"probed": 0}
        result = runner.invoke(app, ["validate-images", "--dry-run", "--limit", "10"])
    assert result.exit_code == 0
    m.assert_called_once_with(dry_run=True, limit=10)


def test_validate_images_command_rejects_zero_limit():
    with patch("pictrip_data.cli.validate_images") as m:
        result = runner.invoke(app, ["validate-images", "--limit", "0"])
    assert result.exit_code != 0
    m.assert_not_called()
