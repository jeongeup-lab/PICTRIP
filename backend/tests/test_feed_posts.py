import pytest
from sqlalchemy import text

from app.core.db import get_db
from app.main import app

SEED_SQL = text("""
INSERT INTO overseas_spots (wikidata_id, name_ko, country_code, country_name_ko,
    description_ko, image_url, image_source_url, fame_score, is_hidden, embedding)
VALUES (:qid, :name, :cc, :cn, :desc, :img, :src, :fame, :hidden,
        CAST(:emb AS halfvec(512)))
""")

_EMBEDDING = "[" + ",".join(["0.1"] * 512) + "]"

SPOT_SQL = text("""
INSERT INTO spots (content_id, content_type_id, title, first_image_url, addr1, mapx, mapy,
    show_flag, lcls_systm1)
VALUES (:cid, 12, :title, :img, 'addr1', 127.0, 37.0, 1, 'NA')
ON CONFLICT (content_id) DO NOTHING
""")

SPOT_EMBEDDING_SQL = text("""
INSERT INTO spot_embeddings (content_id, embedding, image_url)
VALUES (:cid, CAST(:emb AS halfvec(512)), :img)
ON CONFLICT (content_id) DO NOTHING
""")

MATCH_SQL = text("""
INSERT INTO overseas_spot_matches (overseas_id, rank, content_id, distance)
SELECT id, :rank, :cid, :dist FROM overseas_spots WHERE wikidata_id = :qid
""")

_MATCH_SPOTS = ("fp_a", "fp_b", "fp_c")


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
                "emb": _EMBEDDING,
            },
        )
    await db_session.execute(
        text(
            "INSERT INTO overseas_spots (wikidata_id, name_ko, country_code, country_name_ko, "
            "image_url, image_source_url, fame_score, is_hidden) "
            "VALUES ('QN1', '임베딩없음', 'IT', '이탈리아', 'https://img/QN1', "
            "'https://src/QN1', 400, false)"
        )
    )
    for cid in _MATCH_SPOTS:
        img = f"http://kto/{cid}.jpg"
        await db_session.execute(SPOT_SQL, {"cid": cid, "title": f"국내-{cid}", "img": img})
        await db_session.execute(SPOT_EMBEDDING_SQL, {"cid": cid, "emb": _EMBEDDING, "img": img})
    for qid, ranks in (("QF1", 3), ("QF2", 3), ("QJ1", 3), ("QH1", 3), ("QN1", 2)):
        for rank in range(1, ranks + 1):
            await db_session.execute(
                MATCH_SQL,
                {"qid": qid, "rank": rank, "cid": _MATCH_SPOTS[rank - 1], "dist": 0.1 * rank},
            )
    await db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.clear()


async def test_feed_returns_seeded_page(client, seeded):
    res = await client.get("/v1/explore", params={"limit": 2})
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
    res = await client.get("/v1/explore", params={"limit": 10})
    names = [i["nameKo"] for i in res.json()["data"]["items"]]
    assert "숨김" not in names and len(names) == 3


async def test_feed_excludes_posts_without_three_matches(client, seeded):
    """타일이 덜 차는 게시물은 피드에 올리지 않는다 — 매칭 3칸이 슬라이드의 본문이다."""
    res = await client.get("/v1/explore", params={"limit": 10})
    names = [i["nameKo"] for i in res.json()["data"]["items"]]
    assert "임베딩없음" not in names


async def test_feed_inlines_matches(client, seeded):
    """슬라이드마다 /overseas/{id}/matches 를 다시 치면 왕복이 두 번이다."""
    res = await client.get("/v1/explore", params={"limit": 3})
    items = res.json()["data"]["items"]
    assert items
    for item in items:
        assert len(item["matches"]) == 3
        assert {"contentId", "title", "regionLabel", "imageUrl", "overviewFirst"} <= set(
            item["matches"][0]
        )


async def test_feed_drops_posts_whose_match_image_moved(client, db_session, seeded):
    """이미지가 바뀐 스팟은 그 사진으로 닮은 곳이 아니다 — 3칸이 깨진 게시물은 빠진다.

    사전계산 행은 그대로인데 라이브 조인만 탈락하는 구간이 실제로 존재한다
    (일일 동기화가 스팟을 숨기거나 대표사진을 바꾼 뒤 재계산 전). 후보 선정도
    같은 조인을 써야 "매칭 3곳 인라인"이 계약으로 유지된다.
    """
    await db_session.execute(
        text("UPDATE spots SET first_image_url = 'http://kto/moved.jpg' WHERE content_id = 'fp_a'")
    )
    await db_session.commit()

    res = await client.get("/v1/explore", params={"limit": 10})

    assert res.json()["data"]["items"] == []


async def test_feed_only_serves_posts_with_three_live_matches(client, db_session, seeded):
    await db_session.execute(text("UPDATE spots SET show_flag = 0 WHERE content_id = 'fp_c'"))
    await db_session.commit()

    res = await client.get("/v1/explore", params={"limit": 10})

    assert res.json()["data"]["items"] == []


async def test_feed_cursor_no_duplicates_same_seed(client, seeded):
    first = (await client.get("/v1/explore", params={"limit": 2})).json()["data"]
    second = (
        await client.get(
            "/v1/explore", params={"limit": 2, "seed": first["seed"], "cursor": first["nextCursor"]}
        )
    ).json()["data"]
    ids1 = {i["id"] for i in first["items"]}
    ids2 = {i["id"] for i in second["items"]}
    assert not ids1 & ids2 and second["hasMore"] is False


async def test_feed_same_seed_stable_order(client, seeded):
    a = (await client.get("/v1/explore", params={"limit": 3, "seed": "s1"})).json()["data"]
    b = (await client.get("/v1/explore", params={"limit": 3, "seed": "s1"})).json()["data"]
    assert a["items"]
    assert [i["id"] for i in a["items"]] == [i["id"] for i in b["items"]]


async def test_feed_rejects_garbage_cursor(client, seeded):
    res = await client.get("/v1/explore", params={"cursor": "not-a-cursor"})
    body = res.json()
    assert res.status_code == 422
    assert body["error"]["code"] == "VALIDATION_FAILED"


async def test_explore_same_pool(client, seeded):
    res = await client.get("/v1/explore", params={"limit": 30})
    assert len(res.json()["data"]["items"]) == 3


async def test_feed_alias_matches_explore(client, seeded):
    """v0.6.0 빌드는 OTA 를 못 받아 아직 /feed 를 친다 — 별칭이 살아 있어야 한다."""
    seed = (await client.get("/v1/explore", params={"limit": 3})).json()["data"]["seed"]
    a = (await client.get("/v1/explore", params={"limit": 3, "seed": seed})).json()["data"]
    b = (await client.get("/v1/feed", params={"limit": 3, "seed": seed})).json()["data"]
    assert a["items"]
    assert [i["id"] for i in a["items"]] == [i["id"] for i in b["items"]]


async def test_feed_falls_back_to_unfiltered_before_the_first_precompute(
    client, db_session, seeded
):
    """마이그레이션 직후 사전계산 테이블은 비어 있다 — 그때 피드가 빈 화면이면 안 된다."""
    await db_session.execute(text("DELETE FROM overseas_spot_matches"))
    await db_session.commit()

    res = await client.get("/v1/explore", params={"limit": 10})

    names = [i["nameKo"] for i in res.json()["data"]["items"]]
    assert sorted(names) == ["도쿄타워", "루브르", "에펠탑"]
    assert all(item["matches"] == [] for item in res.json()["data"]["items"])
