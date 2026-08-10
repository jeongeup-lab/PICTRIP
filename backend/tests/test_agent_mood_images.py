from __future__ import annotations

from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.kto.client import get_kto
from app.main import app


def _override(db_session: AsyncSession) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: FakeRedis(decode_responses=True)
    app.dependency_overrides[get_kto] = lambda: None


async def _tagged_spot(
    session: AsyncSession,
    cid: str,
    *,
    mood_code: str,
    image: str | None = "http://kto/i.jpg",
    content_type: int = 12,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, "
            "first_image_url, show_flag, lcls_systm1) "
            "VALUES (:cid, :ctype, :cid, '제주특별자치도 제주시 1', :img, 1, 'NA')"
        ),
        {"cid": cid, "ctype": content_type, "img": image},
    )
    await session.execute(
        text(
            "INSERT INTO spot_moods (content_id, mood_id, confidence, source) "
            "SELECT :cid, moods.id, 1.0, 'code' FROM moods WHERE moods.code = :code"
        ),
        {"cid": cid, "code": mood_code},
    )
    await session.flush()


async def test_mood_images_returns_one_photo_per_tagged_mood(
    client, db_session: AsyncSession
) -> None:
    _override(db_session)
    await _tagged_spot(db_session, "m-sea-1", mood_code="sea")
    await _tagged_spot(db_session, "m-sea-2", mood_code="sea")
    await _tagged_spot(db_session, "m-street-1", mood_code="street")

    response = await client.get("/v1/agent/mood-images")

    assert response.status_code == 200
    images = response.json()["data"]["images"]
    codes = [image["code"] for image in images]
    assert sorted(codes) == ["sea", "street"]
    assert len(codes) == len(set(codes))
    assert all(image["imageUrl"] for image in images)


async def test_mood_images_skips_moods_without_usable_photo(
    client, db_session: AsyncSession
) -> None:
    _override(db_session)
    await _tagged_spot(db_session, "m-sea-1", mood_code="sea")
    await _tagged_spot(db_session, "m-night-1", mood_code="night", image=None)
    await _tagged_spot(db_session, "m-hanok-1", mood_code="hanok", content_type=39)

    response = await client.get("/v1/agent/mood-images")

    assert response.status_code == 200
    codes = [image["code"] for image in response.json()["data"]["images"]]
    assert codes == ["sea"]
