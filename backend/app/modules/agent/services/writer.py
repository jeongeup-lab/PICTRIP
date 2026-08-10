from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime

from app.modules.agent.naver import NaverBlogPost
from app.modules.agent.schemas import AgentSpotCard, ChatHistoryItem, QueryIntent

CARDS_MARKER = "[[cards]]"
MAX_SUGGESTIONS = 3
MAX_SUGGESTION_CHARS = 20
_SUGGEST_RE = re.compile(r"^\[\[suggest:\s*(.*?)\s*\]\]$")

SYSTEM_PROMPT = """\
너는 한국 여행 앱 PICTRIP의 어시스턴트다. 아래에 주어지는 도구 결과 JSON만 근거로 한국어 답변 산문을 쓴다.

근거 규칙:
- 도구 결과 JSON에 있는 사실만 쓴다. spots 목록에 없는 장소 이름을 꺼내지 않는다.
- 영업시간·전화번호·가격·요금은 도구 결과에 없으므로 언급하지 않는다.
- blogs 스니펫은 "블로그에서는 ~라는 평이에요" 수준으로만 부드럽게 인용한다. 블로그 문장을 사실 단정으로 옮기지 않는다.
- 별점·평점 표현을 쓰지 않는다. 이모지를 쓰지 않는다.

구조 규칙:
- 핵심 결론 1~2문장으로 시작한다.
- 그 다음 줄에 [[cards]] 를 단독 줄로 정확히 1회 쓴다. 이 자리에 결과 카드가 끼워진다.
- 이어서 spots 의 각 장소마다 "- " 불릿으로 한 줄 팁을 쓴다. 장소 이름은 **굵게** 표기한다.
- 마지막에 한 문장으로 다음 행동을 제안하며 마무리한다.
- 맨 마지막 줄에 [[suggest: 팔로업1 | 팔로업2 | 팔로업3]] 형식으로 이어서 물을 만한 질문을 최대 3개, 각 20자 이내로 쓴다.

문체 규칙:
- 한국어 해요체로 쓴다.
- 서식은 **굵게** 와 "- " 불릿만 쓴다. 제목·표·링크는 쓰지 않는다.
- clientTime 이 있으면 시간대를 감안한다. 늦은 밤이면 야간에 갈 만한지, 이른 아침이면 아침 동선을 짚는 식이다.
- spots 가 비어 있으면 결과가 없다는 사실을 짧게 알리고 조건을 바꿔 보라고 제안만 한다. 장소를 지어내지 않는다.
"""


@dataclass(slots=True)
class WriterDelta:
    text: str


@dataclass(slots=True)
class WriterCards:
    pass


@dataclass(slots=True)
class WriterSuggestions:
    items: list[str]


WriterEvent = WriterDelta | WriterCards | WriterSuggestions


def build_prompt(
    *,
    question: str | None,
    intent: QueryIntent,
    spots: list[AgentSpotCard],
    blog_posts: list[NaverBlogPost],
    client_time: datetime | None,
    history: list[ChatHistoryItem],
) -> tuple[str, str]:
    payload = {
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
    return SYSTEM_PROMPT, json.dumps(payload, ensure_ascii=False)


def parse_suggestions(raw: str) -> list[str]:
    items: list[str] = []
    for part in raw.split("|"):
        cleaned = part.strip()[:MAX_SUGGESTION_CHARS].strip()
        if cleaned and cleaned not in items:
            items.append(cleaned)
        if len(items) == MAX_SUGGESTIONS:
            break
    return items


async def parse_stream(chunks: AsyncIterator[str]) -> AsyncIterator[WriterEvent]:
    line = ""
    sent = 0
    cards_done = False
    body_seen = False
    suggestions: list[str] | None = None

    def end_line() -> list[WriterEvent]:
        nonlocal line, sent, cards_done, body_seen, suggestions
        events: list[WriterEvent] = []
        tail = line[sent:]
        if "[[" in tail:
            if sent:
                events.append(WriterDelta(text="\n"))
            stripped = tail.strip()
            matched = _SUGGEST_RE.match(stripped)
            if matched is not None:
                suggestions = parse_suggestions(matched.group(1))
            elif stripped == CARDS_MARKER and not cards_done:
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
        if "[[" in tail:
            continue
        flushable = tail[:-1] if tail.endswith("[") else tail
        if flushable:
            yield WriterDelta(text=flushable)
            sent += len(flushable)
            if flushable.strip():
                body_seen = True

    tail = line[sent:]
    if "[[" in tail:
        stripped = tail.strip()
        matched = _SUGGEST_RE.match(stripped)
        if matched is not None:
            suggestions = parse_suggestions(matched.group(1))
        elif stripped == CARDS_MARKER and not cards_done:
            cards_done = True
            yield WriterCards()
    elif tail:
        yield WriterDelta(text=tail)
        if tail.strip():
            body_seen = True
    if body_seen and not cards_done:
        yield WriterCards()
    if suggestions:
        yield WriterSuggestions(items=suggestions)
