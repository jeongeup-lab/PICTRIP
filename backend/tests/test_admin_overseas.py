from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.main import app
from app.modules.admin.security import require_admin

_AUTH = {"Authorization": "Basic " + b64encode(b"admin:admin").decode()}

_DIM = 512
_CLOSE = [0.1] * _DIM


def _literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


_INSERT = text(
    "INSERT INTO overseas_spots (wikidata_id, name_ko, country_code, country_name_ko, "
    "description_ko, image_url, image_source_url, fame_score, is_hidden) "
    "VALUES (:qid, :name, :cc, :cn, :desc, :img, :src, :fame, :hidden) RETURNING id"
)


@dataclass
class SeededOverseas:
    ids: list[int]


@pytest.fixture
async def seeded_overseas(db_session: AsyncSession) -> SeededOverseas:
    rows = [
        ("QF1", "루브르", "FR", "프랑스", 200),
        ("QF2", "에펠탑", "FR", "프랑스", 300),
        ("QJ1", "도쿄타워", "JP", "일본", 120),
    ]
    ids: list[int] = []
    for qid, name, cc, cn, fame in rows:
        rid = (
            await db_session.execute(
                _INSERT,
                {
                    "qid": qid,
                    "name": name,
                    "cc": cc,
                    "cn": cn,
                    "desc": None,
                    "img": f"https://img/{qid}",
                    "src": f"https://src/{qid}",
                    "fame": fame,
                    "hidden": False,
                },
            )
        ).scalar_one()
        ids.append(rid)
    await db_session.flush()
    return SeededOverseas(ids=ids)


def _override(db_session: AsyncSession) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_admin] = lambda: "admin"
    app.dependency_overrides[get_redis] = lambda: FakeRedis(decode_responses=True)


async def test_list_overseas_requires_auth(db_session, client, seeded_overseas) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        res = await client.get("/admin/api/overseas")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "ADMIN_UNAUTHORIZED"


async def test_list_overseas_search(db_session, client, seeded_overseas) -> None:
    _override(db_session)
    try:
        res = await client.get("/admin/api/overseas", params={"q": "루브르"}, headers=_AUTH)
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) == 1
    item = items[0]
    assert item["nameKo"] == "루브르"
    assert item.keys() == {"id", "nameKo", "countryNameKo", "imageUrl", "fameScore", "isHidden"}
    assert item["countryNameKo"] == "프랑스"
    assert item["fameScore"] == 200
    assert item["isHidden"] is False


async def test_list_overseas_orders_by_id_and_cursor(db_session, client, seeded_overseas) -> None:
    _override(db_session)
    try:
        page1 = await client.get("/admin/api/overseas", params={"limit": 2}, headers=_AUTH)
        cursor = page1.json()["data"]["nextCursor"]
        page2 = await client.get(
            "/admin/api/overseas", params={"limit": 2, "cursor": cursor}, headers=_AUTH
        )
    finally:
        app.dependency_overrides.clear()

    d1 = page1.json()["data"]
    assert [i["id"] for i in d1["items"]] == seeded_overseas.ids[:2]
    assert d1["nextCursor"] == seeded_overseas.ids[1]

    d2 = page2.json()["data"]
    assert [i["id"] for i in d2["items"]] == seeded_overseas.ids[2:]
    assert d2["nextCursor"] is None


async def test_toggle_visibility(db_session, client, seeded_overseas) -> None:
    oid = seeded_overseas.ids[0]
    _override(db_session)
    try:
        res = await client.put(
            f"/admin/api/overseas/{oid}/visibility", json={"isHidden": True}, headers=_AUTH
        )
        assert res.status_code == 200
        assert res.json()["data"] == {"id": oid, "isHidden": True}

        listed = await client.get("/admin/api/overseas", headers=_AUTH)
        target = next(i for i in listed.json()["data"]["items"] if i["id"] == oid)
        assert target["isHidden"] is True

        back = await client.put(
            f"/admin/api/overseas/{oid}/visibility", json={"isHidden": False}, headers=_AUTH
        )
        assert back.json()["data"]["isHidden"] is False
    finally:
        app.dependency_overrides.clear()


async def test_toggle_visibility_missing_404(db_session, client, seeded_overseas) -> None:
    _override(db_session)
    try:
        res = await client.put(
            "/admin/api/overseas/999999/visibility", json={"isHidden": True}, headers=_AUTH
        )
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "ADMIN_OVERSEAS_NOT_FOUND"


async def test_hidden_spot_excluded_from_feed(db_session, client, seeded_overseas) -> None:
    oid = seeded_overseas.ids[0]
    _override(db_session)
    try:
        await client.put(
            f"/admin/api/overseas/{oid}/visibility", json={"isHidden": True}, headers=_AUTH
        )
        res = await client.get("/v1/explore", params={"limit": 20})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    assert oid not in [i["id"] for i in res.json()["data"]["items"]]


@pytest.fixture
async def matchable_overseas(db_session: AsyncSession) -> int:
    oid = (
        await db_session.execute(
            text(
                "INSERT INTO overseas_spots (wikidata_id, name_ko, country_code, "
                "country_name_ko, image_url, image_source_url, embedding) "
                "VALUES ('QMATCH', '매치명소', 'FR', '프랑스', 'https://img/m', "
                "'https://src/m', CAST(:emb AS halfvec(512))) RETURNING id"
            ),
            {"emb": _literal(_CLOSE)},
        )
    ).scalar_one()
    await db_session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "addr1, mapx, mapy, show_flag) "
            "VALUES ('mm_a', 12, 'title-mm_a', 'http://kto/p.jpg', 'addr1', 127.0, 37.0, 1) "
            "ON CONFLICT (content_id) DO NOTHING"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, embedding) "
            "VALUES ('mm_a', CAST(:emb AS halfvec(512))) ON CONFLICT (content_id) DO NOTHING"
        ),
        {"emb": _literal(_CLOSE)},
    )
    await db_session.flush()
    return int(oid)


async def test_hide_invalidates_match_cache(
    db_session, client, matchable_overseas, redis_client_fake
) -> None:
    oid = matchable_overseas
    _override(db_session)
    app.dependency_overrides[get_redis] = lambda: redis_client_fake
    try:
        primed = await client.get(f"/v1/overseas/{oid}/matches")
        assert primed.status_code == 200
        assert await redis_client_fake.get(f"match:0:{oid}") is not None

        res = await client.put(
            f"/admin/api/overseas/{oid}/visibility", json={"isHidden": True}, headers=_AUTH
        )
        assert res.status_code == 200

        assert await redis_client_fake.get("matching:revision") == "1"
        assert await redis_client_fake.get(f"match:0:{oid}") is not None

        stale = await client.get(f"/v1/overseas/{oid}/matches")
        assert stale.status_code == 404
        assert stale.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()
