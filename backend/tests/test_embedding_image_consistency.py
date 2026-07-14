from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


def _load_revision():
    path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20260714_0019_embedding_image_consistency.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0019", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("migration 0019 could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_revision(connection: Connection, operation: Callable[[], None]) -> None:
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        operation()


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


@pytest.mark.parametrize(("new_url", "suffix"), [(None, "null"), ("", "empty")])
async def test_removing_first_image_clears_embedding_and_failure(
    db_session: AsyncSession, new_url: str | None, suffix: str
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
            "VALUES (:cid, :v, 'https://img/old.jpg')"
        ),
        {"cid": content_id, "v": vector},
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


async def test_migration_queues_stale_preserves_valid_and_clears_no_image(
    db_session: AsyncSession,
) -> None:
    revision = _load_revision()
    connection = await db_session.connection()
    await connection.run_sync(
        lambda sync_connection: _run_revision(sync_connection, revision.downgrade)
    )
    vector = "[" + ",".join(["0.0"] * 512) + "]"
    await db_session.execute(
        text(
            "INSERT INTO spots "
            "(content_id, content_type_id, title, first_image_url, show_flag) VALUES "
            "('migration-stale', 12, 'stale', 'https://img/new.jpg', 1), "
            "('migration-valid-failure', 12, 'valid', 'https://img/current.jpg', 1), "
            "('migration-null-image', 12, 'null', NULL, 1), "
            "('migration-empty-image', 12, 'empty', '', 1)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO spot_embeddings (content_id, embedding, image_url) VALUES "
            "('migration-stale', :v, 'https://img/old.jpg'), "
            "('migration-null-image', :v, 'https://img/old.jpg'), "
            "('migration-empty-image', :v, 'https://img/old.jpg')"
        ),
        {"v": vector},
    )
    await db_session.execute(
        text(
            "INSERT INTO embedding_failures (content_id, reason, attempts) VALUES "
            "('migration-valid-failure', 'clip_error', 7), "
            "('migration-null-image', 'download_failed', 2), "
            "('migration-empty-image', 'download_failed', 3)"
        )
    )

    await connection.run_sync(
        lambda sync_connection: _run_revision(sync_connection, revision.upgrade)
    )

    stale_failure = (
        await db_session.execute(
            text(
                "SELECT reason, attempts FROM embedding_failures "
                "WHERE content_id = 'migration-stale'"
            )
        )
    ).one()
    valid_failure = (
        await db_session.execute(
            text(
                "SELECT reason, attempts FROM embedding_failures "
                "WHERE content_id = 'migration-valid-failure'"
            )
        )
    ).one()
    assert stale_failure.reason == "source_changed"
    assert stale_failure.attempts == 1
    assert valid_failure.reason == "clip_error"
    assert valid_failure.attempts == 7
    assert (
        await db_session.scalar(
            text(
                "SELECT count(*) FROM spot_embeddings "
                "WHERE content_id IN ('migration-stale', 'migration-null-image', "
                "'migration-empty-image')"
            )
        )
        == 0
    )
    assert (
        await db_session.scalar(
            text(
                "SELECT count(*) FROM embedding_failures "
                "WHERE content_id IN ('migration-null-image', 'migration-empty-image')"
            )
        )
        == 0
    )
