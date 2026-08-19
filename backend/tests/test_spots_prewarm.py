from __future__ import annotations

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spots import prewarm_job
from app.modules.spots.prewarm_job import collect_prewarm_targets
from app.modules.spots.services import load_spot_detail, persist_detail_common
from app.web.errors import KtoApiUnavailable, KtoQuotaExhausted

_COMMON = [{"overview": "프리워밍 개요", "homepage": "<a>hp</a>", "tel": "064-000"}]
_INTRO = [{"usetime": "09:30~17:30", "restdate": "매주 월요일"}]


@pytest.fixture
def redis() -> FakeRedis:
    return FakeRedis(decode_responses=True)


class FakeKto:
    def __init__(self, common=None, images=None, intro=None) -> None:
        self._common = common if common is not None else []
        self._images = images if images is not None else []
        self._intro = intro if intro is not None else []
        self.operations: list[str] = []

    async def call(self, service, operation, **params):
        self.operations.append(operation)
        if operation == "detailCommon2":
            return self._common
        if operation == "detailImage2":
            return self._images
        if operation == "detailIntro2":
            return self._intro
        return []


class FailingKto(FakeKto):
    async def call(self, service, operation, **params):
        self.operations.append(operation)
        raise KtoApiUnavailable()


async def _insert_spot(session: AsyncSession, content_id: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, first_image_url, "
            "show_flag, lcls_systm1) VALUES (:c, 12, :t, 'http://kto/first.jpg', 1, 'NA')"
        ),
        {"c": content_id, "t": f"title-{content_id}"},
    )


async def _insert_detail(
    session: AsyncSession,
    content_id: str,
    *,
    overview: str | None,
    intro_data: str | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_details (content_id, content_type_id, overview, intro_data, "
            "cached_at) VALUES (:c, 12, :ov, CAST(:intro AS jsonb), now())"
        ),
        {"c": content_id, "ov": overview, "intro": intro_data},
    )


async def _insert_image(session: AsyncSession, content_id: str, url: str) -> None:
    await session.execute(
        text(
            "INSERT INTO spot_images (content_id, origin_image_url, sort_order) VALUES (:c, :u, 0)"
        ),
        {"c": content_id, "u": url},
    )


@pytest.mark.asyncio
async def test_prewarm_write_keeps_intro_and_images(db_session: AsyncSession) -> None:
    await _insert_spot(db_session, "PW-KEEP")
    await _insert_detail(db_session, "PW-KEEP", overview=None, intro_data='{"usetime": "09:00"}')
    await _insert_image(db_session, "PW-KEEP", "http://kto/gallery.jpg")

    await persist_detail_common(db_session, "PW-KEEP", 12, "새 개요", "http://hp", "02-000")

    row = (
        await db_session.execute(
            text("SELECT overview, intro_data FROM spot_details WHERE content_id = 'PW-KEEP'")
        )
    ).one()
    assert row.overview == "새 개요"
    assert row.intro_data == {"usetime": "09:00"}

    images = (
        (
            await db_session.execute(
                text("SELECT origin_image_url FROM spot_images WHERE content_id = 'PW-KEEP'")
            )
        )
        .scalars()
        .all()
    )
    assert images == ["http://kto/gallery.jpg"]


@pytest.mark.asyncio
async def test_targets_skip_spots_that_already_have_overview(db_session: AsyncSession) -> None:
    await _insert_spot(db_session, "PW-DONE")
    await _insert_detail(db_session, "PW-DONE", overview="이미 있음")
    await _insert_spot(db_session, "PW-TODO")
    await _insert_detail(db_session, "PW-TODO", overview="")
    await _insert_spot(db_session, "PW-NONE")

    targets = await collect_prewarm_targets(db_session)

    assert [content_id for content_id, _ in targets] == ["PW-NONE", "PW-TODO"]
    assert all(content_type_id == 12 for _, content_type_id in targets)


@pytest.mark.asyncio
async def test_prewarmed_overview_still_fetches_intro_on_demand(
    db_session: AsyncSession, redis: FakeRedis
) -> None:
    await _insert_spot(db_session, "PW-INTRO")
    await persist_detail_common(db_session, "PW-INTRO", 12, "프리워밍 개요", None, None)
    kto = FakeKto(_COMMON, [], _INTRO)

    row = await load_spot_detail(db_session, kto, redis, "PW-INTRO", require_intro=True)

    assert "detailIntro2" in kto.operations
    assert row.intro is not None
    assert row.intro.usetime == "09:30~17:30"


@pytest.mark.asyncio
async def test_prewarmed_overview_serves_without_kto_when_intro_not_needed(
    db_session: AsyncSession, redis: FakeRedis
) -> None:
    await _insert_spot(db_session, "PW-OVERVIEW")
    await persist_detail_common(db_session, "PW-OVERVIEW", 12, "프리워밍 개요", None, None)
    kto = FakeKto(_COMMON, [], _INTRO)

    row = await load_spot_detail(db_session, kto, redis, "PW-OVERVIEW")

    assert kto.operations == []
    assert row.detail_status == "fresh"
    assert row.overview == "프리워밍 개요"


@pytest.mark.asyncio
async def test_intro_fetch_failure_falls_back_to_prewarmed_overview(
    db_session: AsyncSession, redis: FakeRedis
) -> None:
    await _insert_spot(db_session, "PW-FAIL")
    await persist_detail_common(db_session, "PW-FAIL", 12, "프리워밍 개요", None, None)

    row = await load_spot_detail(db_session, FailingKto(), redis, "PW-FAIL", require_intro=True)

    assert row.detail_status == "stale"
    assert row.overview == "프리워밍 개요"


class QuotaKto(FakeKto):
    def __init__(self, allowance: int) -> None:
        super().__init__(common=_COMMON)
        self.allowance = allowance

    async def call(self, service, operation, **params):
        if len(self.operations) >= self.allowance:
            self.operations.append(operation)
            raise KtoQuotaExhausted()
        return await super().call(service, operation, **params)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_prewarm_stops_when_the_daily_quota_runs_out(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """쿼터가 끊긴 뒤에도 남은 타깃을 계속 때리면 그날 라이브 조회분까지 태운다."""
    targets = [(f"pw-{i}", 12) for i in range(10)]
    kto = QuotaKto(allowance=3)
    monkeypatch.setattr(prewarm_job, "KtoClient", lambda: kto)
    monkeypatch.setattr(prewarm_job, "collect_prewarm_targets", _fixed_targets(targets))
    monkeypatch.setattr(prewarm_job, "persist_detail_common", _noop_persist)
    monkeypatch.setattr(prewarm_job, "async_session_factory", _session_factory(db_session))

    result = await prewarm_job.run_prewarm_job(limit=10)

    assert result.written == 3
    assert result.by_status[prewarm_job.QUOTA_SKIPPED] == 7
    assert len(kto.operations) == 4


def _fixed_targets(targets):
    async def _collect(session, *, limit=None):
        return targets[:limit] if limit else targets

    return _collect


async def _noop_persist(session, content_id, content_type_id, overview, homepage, tel):
    return None


def _session_factory(session):
    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *exc):
            return False

    return lambda: _Ctx()
