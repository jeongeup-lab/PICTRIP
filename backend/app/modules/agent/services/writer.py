from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime

from app.modules.agent.schemas import AgentSpotCard, ChatHistoryItem, QueryIntent
from app.naver.client import NaverBlogPost

CARDS_MARKER = "[[cards]]"

FULLWIDTH_OPEN = "\uff3b"
FULLWIDTH_CLOSE = "\uff3d"
LENTICULAR_OPEN = "\u3010"
LENTICULAR_CLOSE = "\u3011"
TORTOISE_OPEN = "\u3014"
TORTOISE_CLOSE = "\u3015"

_MARKER_OPENERS = ("[[", FULLWIDTH_OPEN * 2, LENTICULAR_OPEN, TORTOISE_OPEN)
_PARTIAL_OPENERS = ("[", FULLWIDTH_OPEN)
_BRACKET_FOLD = str.maketrans(
    {
        FULLWIDTH_OPEN: "[",
        FULLWIDTH_CLOSE: "]",
        LENTICULAR_OPEN: "[",
        LENTICULAR_CLOSE: "]",
        TORTOISE_OPEN: "[",
        TORTOISE_CLOSE: "]",
    }
)
_CARDS_FORMS = frozenset({CARDS_MARKER, "[cards]"})


def _opens_marker(text: str) -> bool:
    return any(opener in text for opener in _MARKER_OPENERS)


def _is_cards_marker(text: str) -> bool:
    return text.strip().translate(_BRACKET_FOLD) in _CARDS_FORMS


SYSTEM_PROMPT = """\
너는 한국 여행 앱 PICTRIP의 어시스턴트다. 아래에 주어지는 도구 결과 JSON만 근거로 한국어 답변 산문을 쓴다.

근거 규칙:
- 도구 결과 JSON에 있는 사실만 쓴다. spots 목록에 없는 장소 이름을 꺼내지 않는다.
- 영업시간·전화번호·가격·요금은 도구 결과에 없으므로 언급하지 않는다.
- blogs 스니펫은 그 장소나 지역을 실제로 다룰 때만 "블로그에서는 ~라는 평이에요" 수준으로 부드럽게 인용한다. 관련 없어 보이면 아예 언급하지 않는다. 블로그 문장을 사실 단정으로 옮기지 않는다.
- 별점·평점 표현을 쓰지 않는다. 이모지를 쓰지 않는다.

구조 규칙:
- 핵심 결론 1~2문장으로 시작한다.
- 그 다음 줄에 [[cards]] 를 단독 줄로 정확히 1회 쓴다. 이 자리에 결과 카드가 끼워진다.
- 이어서 "- " 불릿으로 한 줄 팁을 쓴다. 장소 이름은 **굵게** 표기한다.
- **불릿은 최대 5개다.** spots 가 그보다 많으면 앞에서부터 5곳만 고르고, 나머지는 카드로 볼 수 있다고 한 문장으로 알린다. 목록을 끝까지 나열하지 않는다.
- 마지막에 한 문장으로 다음 행동을 제안하며 마무리한다.

문체 규칙:
- 한국어 해요체로만 쓴다. "~습니다"·"~입니다" 같은 합쇼체를 섞지 않는다.
- 서식은 **굵게** 와 "- " 불릿만 쓴다. 제목·표·링크는 쓰지 않는다.
- clientTime 이 있으면 시간대를 감안한다. 늦은 밤이면 야간에 갈 만한지, 이른 아침이면 아침 동선을 짚는 식이다.
- spots 가 비어 있으면 결과가 없다는 사실을 짧게 알리고 조건을 바꿔 보라고 제안만 한다. 장소를 지어내지 않는다.
- situation 이 있으면 그것이 이번 턴에 실제로 벌어진 일이다. spots 가 비었다고 무조건 "결과가 없다"고
  쓰지 말고 situation 에 맞춰 쓴다. 못 하는 요구였다면 무엇을 못 하는지 밝히고, 대신 할 수 있는 것을
  한 가지 제안하며 마무리한다. [[cards]] 는 spots 가 비어 있으면 쓰지 않는다.
"""

REMINDER = """\
지금부터 답변을 쓴다. 아래 세 가지를 반드시 지킨다.
- spots 목록에 없는 장소 이름을 절대 쓰지 않는다.
- 영업시간·전화번호·요금은 언급하지 않는다.
- [[cards]] 를 단독 줄로 정확히 1회 쓴다."""


@dataclass(slots=True)
class WriterDelta:
    text: str


@dataclass(slots=True)
class WriterCards:
    pass


WriterEvent = WriterDelta | WriterCards


def build_prompt(
    *,
    question: str | None,
    intent: QueryIntent,
    spots: list[AgentSpotCard],
    blog_posts: list[NaverBlogPost],
    client_time: datetime | None,
    history: list[ChatHistoryItem],
    situation: str | None = None,
) -> tuple[str, str]:
    payload = {
        "situation": situation,
        "question": question,
        "clientTime": client_time.isoformat() if client_time is not None else None,
        "intent": intent.model_dump(exclude_defaults=True),
        "spots": [
            {
                "title": spot.title,
                "region": spot.regionLabel,
                "tag": spot.tag,
                "hasCrowd": spot.hasCrowd,
            }
            for spot in spots
        ],
        "blogs": [
            {"title": post.title, "summary": post.description, "date": post.postdate}
            for post in blog_posts
        ],
        "history": [{"role": item.role, "text": item.text} for item in history],
    }
    body = json.dumps(payload, ensure_ascii=False)
    return SYSTEM_PROMPT, f"{body}\n\n{REMINDER}"


async def parse_stream(chunks: AsyncIterator[str]) -> AsyncIterator[WriterEvent]:
    line = ""
    sent = 0
    cards_done = False
    body_seen = False

    def end_line() -> list[WriterEvent]:
        nonlocal line, sent, cards_done, body_seen
        events: list[WriterEvent] = []
        tail = line[sent:]
        if _opens_marker(tail):
            if sent:
                events.append(WriterDelta(text="\n"))
            if _is_cards_marker(tail) and not cards_done:
                cards_done = True
                events.append(WriterCards())
        else:
            events.append(WriterDelta(text=f"{tail}\n"))
            if line.strip():
                body_seen = True
            elif body_seen and not cards_done:
                cards_done = True
                events.append(WriterCards())
        line = ""
        sent = 0
        return events

    async for chunk in chunks:
        for ch in chunk:
            if ch != "\n":
                line += ch
                continue
            for event in end_line():
                yield event
        tail = line[sent:]
        if _opens_marker(tail):
            continue
        flushable = tail[:-1] if tail.endswith(_PARTIAL_OPENERS) else tail
        if flushable:
            yield WriterDelta(text=flushable)
            sent += len(flushable)
            if flushable.strip():
                body_seen = True

    tail = line[sent:]
    if _opens_marker(tail):
        if _is_cards_marker(tail) and not cards_done:
            cards_done = True
            yield WriterCards()
    elif tail:
        yield WriterDelta(text=tail)
        if tail.strip():
            body_seen = True
    if body_seen and not cards_done:
        yield WriterCards()
