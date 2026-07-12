import pytest
from sqlalchemy import text

from app.core.db import get_db
from app.main import app

SEED_SQL = text("""
INSERT INTO overseas_spots (wikidata_id, name_ko, country_code, country_name_ko,
    description_ko, image_url, image_source_url, fame_score, is_hidden)
VALUES (:qid, :name, :cc, :cn, :desc, :img, :src, :fame, :hidden)
""")


@pytest.fixture
async def seeded(db_session):
    rows = [
        ("QF1", "루브르", "FR", "프랑스", "파리의 미술관", 200, False),
        ("QF2", "에펠탑", "FR", "프랑스", None, 300, False),
        ("QJ1", "도쿄타워", "JP", "일본", "도쿄의 전파탑", 120, False),
        ("QH1", "숨김", "JP", "일본", None, 500, True),
    ]
    for qid, name, cc, cn, desc, fame, hidden in rows:
        await db_session.execute(
            SEED_SQL,
            {
                "qid": qid,
                "name": name,
                "cc": cc,
                "cn": cn,
                "desc": desc,
                "img": f"https://img/{qid}",
                "src": f"https://src/{qid}",
                "fame": fame,
                "hidden": hidden,
            },
        )
    await db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.clear()


async def test_feed_returns_seeded_page(client, seeded):
    res = await client.get("/v1/feed", params={"limit": 2})
    body = res.json()
    assert res.status_code == 200 and body["error"] is None
    data = body["data"]
    assert data["seed"] and len(data["items"]) == 2 and data["hasMore"] is True
    assert {
        "id",
        "nameKo",
        "countryCode",
        "countryNameKo",
        "descriptionKo",
        "imageUrl",
        "imageAuthor",
        "imageLicense",
        "imageLicenseUrl",
        "imageSourceUrl",
    } <= set(data["items"][0])


async def test_feed_excludes_hidden(client, seeded):
    res = await client.get("/v1/feed", params={"limit": 10})
    names = [i["nameKo"] for i in res.json()["data"]["items"]]
    assert "숨김" not in names and len(names) == 3


async def test_feed_cursor_no_duplicates_same_seed(client, seeded):
    first = (await client.get("/v1/feed", params={"limit": 2})).json()["data"]
    second = (
        await client.get(
            "/v1/feed", params={"limit": 2, "seed": first["seed"], "cursor": first["nextCursor"]}
        )
    ).json()["data"]
    ids1 = {i["id"] for i in first["items"]}
    ids2 = {i["id"] for i in second["items"]}
    assert not ids1 & ids2 and second["hasMore"] is False


async def test_feed_same_seed_stable_order(client, seeded):
    a = (await client.get("/v1/feed", params={"limit": 3, "seed": "s1"})).json()["data"]
    b = (await client.get("/v1/feed", params={"limit": 3, "seed": "s1"})).json()["data"]
    assert [i["id"] for i in a["items"]] == [i["id"] for i in b["items"]]


async def test_feed_rejects_garbage_cursor(client, seeded):
    res = await client.get("/v1/feed", params={"cursor": "not-a-cursor"})
    body = res.json()
    assert res.status_code == 422
    assert body["error"]["code"] == "VALIDATION_FAILED"


async def test_explore_same_pool(client, seeded):
    res = await client.get("/v1/explore", params={"limit": 30})
    assert len(res.json()["data"]["items"]) == 3
