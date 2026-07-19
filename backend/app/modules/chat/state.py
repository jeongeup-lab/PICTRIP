"""CHT session state — Redis JSON, TTL-scoped, guest-anonymous.

A session is the accumulating condition stack behind the 스무고개 board plus the
axes already asked (so the board never re-asks the same axis).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field

from redis.asyncio import Redis

from app.config import settings

_KEY = "chat:{sid}"


@dataclass
class Condition:
    id: str
    kind: str
    label: str
    region_cd: str | None = None
    sigungu_cd: str | None = None
    category: str | None = None
    keyword: str | None = None
    exclude: bool = False


@dataclass
class ChatSession:
    session_id: str
    turns: int = 0
    conditions: list[Condition] = field(default_factory=list)
    asked_axes: list[str] = field(default_factory=list)


def new_session() -> ChatSession:
    return ChatSession(session_id=uuid.uuid4().hex)


async def load_session(redis: Redis, session_id: str) -> ChatSession | None:
    raw = await redis.get(_KEY.format(sid=session_id))
    if raw is None:
        return None
    data = json.loads(raw)
    return ChatSession(
        session_id=data["session_id"],
        turns=int(data["turns"]),
        conditions=[Condition(**c) for c in data["conditions"]],
        asked_axes=list(data.get("asked_axes", [])),
    )


async def save_session(redis: Redis, session: ChatSession) -> None:
    await redis.set(
        _KEY.format(sid=session.session_id),
        json.dumps(asdict(session), ensure_ascii=False),
        ex=settings.CHAT_SESSION_TTL_SECONDS,
    )
