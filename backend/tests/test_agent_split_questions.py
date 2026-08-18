from __future__ import annotations

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.schemas import QueryIntent
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import intent as intent_service

REGION = "전라남도 여수시"


async def _seed(session: AsyncSession, cid: str, title: str, l1: str, l2: str | None) -> None:
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, first_image_url, "
            "show_flag, lcls_systm1, lcls_systm2, mapx, mapy) VALUES "
            "(:c, 12, :t, :a, 'http://kto/i.jpg', 1, :l1, :l2, 127.7, 34.7)"
        ),
        {"c": cid, "t": title, "a": f"{REGION} 어딘가", "l1": l1, "l2": l2},
    )


@pytest.fixture
async def seeded(db_session: AsyncSession) -> AsyncSession:
    await db_session.execute(
        text(
            "INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES ('46', '전라남도') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO sigungus (ldong_signgu_cd, ldong_regn_cd, ldong_signgu_nm) "
            "VALUES ('46130', '46', '여수시') ON CONFLICT DO NOTHING"
        )
    )
    await _seed(db_session, "9300001", "여수 바다카페", "FD", "FD05")
    await _seed(db_session, "9300002", "여수 오션커피", "FD", "FD05")
    await _seed(db_session, "9300003", "오동도", "NA", None)
    await _seed(db_session, "9300004", "여수해상케이블카", "NA", None)
    return db_session


def _intents(monkeypatch: pytest.MonkeyPatch, by_question: dict[str, QueryIntent]) -> list[str]:
    asked: list[str] = []

    async def fake(question: str, **_kw: object) -> QueryIntent:
        asked.append(question)
        return by_question.get(question, QueryIntent())

    monkeypatch.setattr(intent_service, "extract_intent", fake)
    return asked


async def test_a_question_that_asks_two_things_is_answered_with_both(
    seeded: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = _intents(
        monkeypatch,
        {
            "여수 카페랑 볼거리": QueryIntent(subQuestions=["여수 카페", "여수 볼거리"]),
            "여수 카페": QueryIntent(regionHints=["여수"], categoryKeywords=["카페"]),
            "여수 볼거리": QueryIntent(regionHints=["여수"]),
        },
    )

    result = await ask_service.ask(
        seeded,
        FakeRedis(decode_responses=True),
        None,
        question="여수 카페랑 볼거리",
        lat=34.7,
        lng=127.7,
        image_bytes=None,
        image_mime=None,
    )

    titles = {spot.title for spot in result.spots}
    assert "여수 바다카페" in titles, "카페 쪽 결과가 있어야 한다"
    assert "오동도" in titles, "볼거리 쪽 결과도 함께 와야 한다"
    assert asked[0] == "여수 카페랑 볼거리"


async def test_a_single_ask_is_not_split_because_that_only_duplicates_results(
    seeded: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = _intents(
        monkeypatch,
        {"여수 카페": QueryIntent(regionHints=["여수"], categoryKeywords=["카페"])},
    )

    await ask_service.ask(
        seeded,
        FakeRedis(decode_responses=True),
        None,
        question="여수 카페",
        lat=None,
        lng=None,
        image_bytes=None,
        image_mime=None,
    )

    assert asked == ["여수 카페"], "쪼갤 게 없으면 한 번만 묻는다"
