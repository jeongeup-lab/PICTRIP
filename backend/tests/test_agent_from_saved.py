from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.tools import CATALOG, ToolContext
from app.security.jwt import _signing_key, get_optional_user_id

pytestmark = pytest.mark.asyncio


def _vec(*values: float) -> str:
    padded = [*values, *([0.0] * (512 - len(values)))]
    return "[" + ",".join(str(value) for value in padded) + "]"


async def _spot(session: AsyncSession, cid: str, *, title: str, vec: str | None = None) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, mapx, mapy) "
            "VALUES (:c, 12, :t, '경상남도 통영시 1', 'http://kto/i.jpg', 1, 'NA', 128.4, 34.8)"
        ),
        {"c": cid, "t": title},
    )
    if vec is not None:
        await session.execute(
            text("INSERT INTO spot_embeddings (content_id, embedding) VALUES (:c, :v)"),
            {"c": cid, "v": vec},
        )


async def _user(session: AsyncSession) -> int:
    row = (
        await session.execute(
            text("INSERT INTO users (email, name) VALUES (:e, '이신성') RETURNING id"),
            {"e": f"saved-{uuid.uuid4().hex[:10]}@e.st"},
        )
    ).first()
    assert row is not None
    return int(row.id)


async def _save(session: AsyncSession, *, user_id: int, cid: str) -> None:
    await session.execute(
        text("INSERT INTO user_saved_spots (user_id, content_id) VALUES (:u, :c)"),
        {"u": user_id, "c": cid},
    )


async def test_from_saved_tells_the_model_the_caller_is_anonymous(
    db_session: AsyncSession, redis_client_fake
) -> None:
    """익명 사용자에게 저장한 곳을 못 찾았다고 답하면 로그인하라는 말이 안 나온다."""
    ctx = ToolContext(session=db_session, redis=redis_client_fake, kto=None)

    result = await CATALOG["from_saved"].run(ctx, {})

    assert result.rows == []
    assert "로그인" in result.observation
    assert result.fact is not None and "로그인하면" in result.fact


async def test_from_saved_needs_enough_seeds_to_read_a_taste(
    db_session: AsyncSession, redis_client_fake
) -> None:
    """한 곳 저장한 사람의 평균 벡터는 그 한 곳일 뿐이다."""
    user_id = await _user(db_session)
    await _spot(db_session, "fs-1", title="통영항", vec=_vec(1.0, 0.0))
    await _save(db_session, user_id=user_id, cid="fs-1")
    await db_session.flush()
    ctx = ToolContext(session=db_session, redis=redis_client_fake, kto=None, user_id=user_id)

    result = await CATALOG["from_saved"].run(ctx, {})

    assert result.rows == []
    assert result.fact is not None and "3곳 이상 저장하면" in result.fact


async def test_from_saved_matches_the_centroid_without_returning_the_seeds(
    db_session: AsyncSession, redis_client_fake
) -> None:
    """저장한 곳을 그대로 돌려주면 추천이 아니라 저장 목록이다."""
    user_id = await _user(db_session)
    for index in range(3):
        await _spot(db_session, f"fs-s{index}", title=f"저장{index}", vec=_vec(1.0, 0.0))
        await _save(db_session, user_id=user_id, cid=f"fs-s{index}")
    await _spot(db_session, "fs-near", title="닮은곳", vec=_vec(0.99, 0.1))
    await _spot(db_session, "fs-far", title="먼곳", vec=_vec(0.0, 1.0))
    await db_session.flush()
    ctx = ToolContext(session=db_session, redis=redis_client_fake, kto=None, user_id=user_id)

    result = await CATALOG["from_saved"].run(ctx, {})

    titles = [row.title for row in result.rows]
    assert titles[0] == "닮은곳"
    assert not any(title.startswith("저장") for title in titles)


async def test_from_saved_counts_only_seeds_that_have_an_embedding(
    db_session: AsyncSession, redis_client_fake
) -> None:
    """임베딩 없는 저장 항목은 centroid 에서 조용히 빠져 시드 하한을 우회한다."""
    user_id = await _user(db_session)
    await _spot(db_session, "fs-e1", title="벡터있음", vec=_vec(1.0, 0.0))
    for index in range(3):
        await _spot(db_session, f"fs-n{index}", title=f"벡터없음{index}")
    for cid in ("fs-e1", "fs-n0", "fs-n1", "fs-n2"):
        await _save(db_session, user_id=user_id, cid=cid)
    await db_session.flush()
    ctx = ToolContext(session=db_session, redis=redis_client_fake, kto=None, user_id=user_id)

    result = await CATALOG["from_saved"].run(ctx, {})

    assert result.rows == []
    assert result.fact is not None and "1곳" in result.fact


async def test_optional_auth_treats_an_expired_token_as_anonymous() -> None:
    """만료 토큰이 401 이면 여행 채팅 전체가 죽는다 — 갱신 인터셉터가 없는 raw fetch 다."""
    past = datetime.now(tz=UTC) - timedelta(hours=1)
    key, algo = _signing_key()
    expired = jwt.encode(
        {
            "sub": "1",
            "iat": int(past.timestamp()),
            "exp": int(past.timestamp()) + 60,
            "type": "access",
        },
        key,
        algorithm=algo,
    )

    assert await get_optional_user_id(f"Bearer {expired}") is None
