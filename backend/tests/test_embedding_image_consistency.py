from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_first_image_change_invalidates_embedding_and_queues_retry(
    db_session: AsyncSession,
) -> None:
    vector = "[" + ",".join(["0.0"] * 512) + "]"
    await db_session.execute(
        text(
            "INSERT INTO spots "
            "(content_id, content_type_id, title, first_image_url, show_flag) "
            "VALUES ('trigger-image-change', 12, 'trigger', 'https://img/old.jpg', 1)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, embedding, image_url) "
            "VALUES ('trigger-image-change', :v, 'https://img/old.jpg')"
        ),
        {"v": vector},
    )
    await db_session.execute(
        text(
            "INSERT INTO embedding_failures (content_id, reason, attempts) "
            "VALUES ('trigger-image-change', 'download_failed', 4)"
        )
    )

    await db_session.execute(
        text(
            "UPDATE spots SET first_image_url = 'https://img/old.jpg' "
            "WHERE content_id = 'trigger-image-change'"
        )
    )
    assert (
        await db_session.scalar(
            text("SELECT count(*) FROM spot_embeddings WHERE content_id = 'trigger-image-change'")
        )
        == 1
    )
    original_failure = (
        await db_session.execute(
            text(
                "SELECT reason, attempts FROM embedding_failures "
                "WHERE content_id = 'trigger-image-change'"
            )
        )
    ).one()
    assert original_failure.reason == "download_failed"
    assert original_failure.attempts == 4

    await db_session.execute(
        text(
            "UPDATE spots SET first_image_url = 'https://img/new.jpg' "
            "WHERE content_id = 'trigger-image-change'"
        )
    )
    assert (
        await db_session.scalar(
            text("SELECT count(*) FROM spot_embeddings WHERE content_id = 'trigger-image-change'")
        )
        == 0
    )
    queued_failure = (
        await db_session.execute(
            text(
                "SELECT reason, attempts, last_error FROM embedding_failures "
                "WHERE content_id = 'trigger-image-change'"
            )
        )
    ).one()
    assert queued_failure.reason == "source_changed"
    assert queued_failure.attempts == 4
    assert queued_failure.last_error is None


@pytest.mark.parametrize(
    ("new_url", "embedding_url", "suffix"),
    [(None, None, "null"), ("", "", "empty")],
)
async def test_removing_first_image_clears_embedding_and_failure(
    db_session: AsyncSession,
    new_url: str | None,
    embedding_url: str | None,
    suffix: str,
) -> None:
    content_id = f"trigger-image-{suffix}"
    vector = "[" + ",".join(["0.0"] * 512) + "]"
    await db_session.execute(
        text(
            "INSERT INTO spots "
            "(content_id, content_type_id, title, first_image_url, show_flag) "
            "VALUES (:cid, 12, 'trigger', 'https://img/old.jpg', 1)"
        ),
        {"cid": content_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, embedding, image_url) "
            "VALUES (:cid, :v, :embedding_url)"
        ),
        {"cid": content_id, "v": vector, "embedding_url": embedding_url},
    )
    await db_session.execute(
        text("INSERT INTO embedding_failures (content_id, reason) VALUES (:cid, 'clip_error')"),
        {"cid": content_id},
    )

    await db_session.execute(
        text("UPDATE spots SET first_image_url = :url WHERE content_id = :cid"),
        {"url": new_url, "cid": content_id},
    )

    assert (
        await db_session.scalar(
            text("SELECT count(*) FROM spot_embeddings WHERE content_id = :cid"),
            {"cid": content_id},
        )
        == 0
    )
    assert (
        await db_session.scalar(
            text("SELECT count(*) FROM embedding_failures WHERE content_id = :cid"),
            {"cid": content_id},
        )
        == 0
    )


async def test_overseas_image_change_invalidates_embedding(
    db_session: AsyncSession,
) -> None:
    vector = "[" + ",".join(["0.0"] * 512) + "]"
    overseas_id = await db_session.scalar(
        text(
            "INSERT INTO overseas_spots "
            "(wikidata_id, name_ko, country_code, country_name_ko, image_url, "
            "image_source_url, embedding) VALUES "
            "('Q-trigger-overseas', '해외 테스트', 'FR', '프랑스', "
            "'https://img/overseas-old.jpg', 'https://source/overseas', "
            "CAST(:v AS halfvec(512))) RETURNING id"
        ),
        {"v": vector},
    )

    await db_session.execute(
        text("UPDATE overseas_spots SET image_url = 'https://img/overseas-old.jpg' WHERE id = :id"),
        {"id": overseas_id},
    )
    assert await db_session.scalar(
        text("SELECT embedding IS NOT NULL FROM overseas_spots WHERE id = :id"),
        {"id": overseas_id},
    )

    await db_session.execute(
        text("UPDATE overseas_spots SET image_url = 'https://img/overseas-new.jpg' WHERE id = :id"),
        {"id": overseas_id},
    )
    assert not await db_session.scalar(
        text("SELECT embedding IS NOT NULL FROM overseas_spots WHERE id = :id"),
        {"id": overseas_id},
    )
