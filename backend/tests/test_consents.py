from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.security.jwt import create_access_token


@pytest_asyncio.fixture(autouse=True)
async def override_db_and_seed() -> AsyncIterator[AsyncSession]:
    from app.core.db import get_db
    from app.main import app

    eng = create_async_engine(settings.sqlalchemy_database_url, poolclass=NullPool)
    async with eng.connect() as conn:
        tx = await conn.begin()
        try:
            seed = AsyncSession(
                bind=conn,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )

            async def _override() -> AsyncIterator[AsyncSession]:
                session = AsyncSession(
                    bind=conn,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                )
                try:
                    yield session
                finally:
                    await session.close()

            app.dependency_overrides[get_db] = _override
            try:
                yield seed
            finally:
                await seed.close()
                app.dependency_overrides.pop(get_db, None)
        finally:
            if tx.is_active:
                await tx.rollback()
    await eng.dispose()


async def _seed_user(session: AsyncSession) -> int:
    email = f"consent-{uuid.uuid4().hex[:10]}@e.st"
    row = (
        await session.execute(
            text("INSERT INTO users (email, name) VALUES (:e, 'Consenter') RETURNING id"),
            {"e": email},
        )
    ).first()
    assert row is not None
    await session.commit()
    return int(row.id)


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user_id)}"}


async def test_put_consents_creates_and_echoes(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)

    resp = await client.put(
        "/v1/users/me/consents",
        headers=_auth(uid),
        json={"locationConsent": True, "termsVersion": "v1.0"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    data = body["data"]
    assert data["locationConsent"] is True
    assert "photoConsent" not in data
    assert data["termsVersion"] == "v1.0"
    assert data["consentedAt"] is not None


async def test_put_consents_ignores_a_retired_photo_consent_field(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)

    resp = await client.put(
        "/v1/users/me/consents",
        headers=_auth(uid),
        json={"locationConsent": True, "photoConsent": True, "termsVersion": "v2.0"},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["locationConsent"] is True
    assert "photoConsent" not in data
    assert data["termsVersion"] == "v2.0"


async def test_put_consents_leaves_the_retired_column_on_its_default(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)

    resp = await client.put(
        "/v1/users/me/consents",
        headers=_auth(uid),
        json={"locationConsent": True, "termsVersion": "v1.0"},
    )
    assert resp.status_code == 200

    stored = (
        await override_db_and_seed.execute(
            text("SELECT photo_consent FROM user_consents WHERE user_id = :u"), {"u": uid}
        )
    ).scalar_one()
    assert stored is False


async def test_put_consents_is_idempotent_upsert(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)

    first = await client.put(
        "/v1/users/me/consents",
        headers=_auth(uid),
        json={"locationConsent": True, "termsVersion": "v1.0"},
    )
    assert first.status_code == 200

    second = await client.put(
        "/v1/users/me/consents",
        headers=_auth(uid),
        json={"locationConsent": False, "termsVersion": "v3.0"},
    )
    assert second.status_code == 200
    data = second.json()["data"]
    assert data["locationConsent"] is False
    assert data["termsVersion"] == "v3.0"

    count = (
        await override_db_and_seed.execute(
            text("SELECT count(*) AS n FROM user_consents WHERE user_id = :u"), {"u": uid}
        )
    ).scalar_one()
    assert count == 1


async def test_put_consents_without_auth_returns_401(client: AsyncClient) -> None:
    resp = await client.put(
        "/v1/users/me/consents",
        json={"locationConsent": True, "termsVersion": "v1.0"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


async def test_get_consents_returns_defaults_when_no_row(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)

    resp = await client.get("/v1/users/me/consents", headers=_auth(uid))

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data == {
        "locationConsent": False,
        "termsVersion": None,
        "consentedAt": None,
        "aiTransferConsent": False,
        "aiTransferVersion": None,
        "aiTransferConsentedAt": None,
    }


async def test_get_consents_echoes_persisted_row(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await client.put(
        "/v1/users/me/consents",
        headers=_auth(uid),
        json={"locationConsent": True, "termsVersion": "v9.0"},
    )

    resp = await client.get("/v1/users/me/consents", headers=_auth(uid))

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["locationConsent"] is True
    assert data["termsVersion"] == "v9.0"
    assert data["consentedAt"] is not None


async def test_get_consents_without_auth_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/v1/users/me/consents")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


async def test_ai_transfer_consent_records_version_and_time(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)

    resp = await client.put(
        "/v1/users/me/consents/ai-transfer",
        headers=_auth(uid),
        json={"granted": True, "version": "2026-08-22"},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["aiTransferConsent"] is True
    assert data["aiTransferVersion"] == "2026-08-22"
    assert data["aiTransferConsentedAt"] is not None


async def test_ai_transfer_withdrawal_clears_the_evidence(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await client.put(
        "/v1/users/me/consents/ai-transfer",
        headers=_auth(uid),
        json={"granted": True, "version": "2026-08-22"},
    )

    resp = await client.put(
        "/v1/users/me/consents/ai-transfer",
        headers=_auth(uid),
        json={"granted": False, "version": "2026-08-22"},
    )

    data = resp.json()["data"]
    assert data["aiTransferConsent"] is False
    assert data["aiTransferVersion"] is None
    assert data["aiTransferConsentedAt"] is None


async def test_location_sync_does_not_clobber_ai_transfer_consent(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    """위치 동의는 화면 포커스마다 전체 PUT 으로 덮어쓴다 — 국외이전 동의가 같이 지워지면 안 된다."""
    uid = await _seed_user(override_db_and_seed)
    await client.put(
        "/v1/users/me/consents/ai-transfer",
        headers=_auth(uid),
        json={"granted": True, "version": "2026-08-22"},
    )

    await client.put(
        "/v1/users/me/consents",
        headers=_auth(uid),
        json={"locationConsent": False, "termsVersion": "v1.0"},
    )

    resp = await client.get("/v1/users/me/consents", headers=_auth(uid))
    data = resp.json()["data"]
    assert data["locationConsent"] is False
    assert data["aiTransferConsent"] is True
    assert data["aiTransferVersion"] == "2026-08-22"


async def test_ai_transfer_consent_without_auth_returns_401(client: AsyncClient) -> None:
    resp = await client.put(
        "/v1/users/me/consents/ai-transfer", json={"granted": True, "version": "2026-08-22"}
    )
    assert resp.status_code == 401
