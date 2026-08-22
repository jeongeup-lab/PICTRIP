from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
from pydantic import BaseModel
from redis.asyncio import Redis

from app.core.db import AsyncSession
from app.core.logging import get_logger, get_trace_id
from app.kto.client import KtoClient
from app.modules.agent import llm, naver, search
from app.modules.agent import outcome as outcome_service
from app.modules.agent.emitter import Emitter
from app.modules.agent.errors import AgentWriterUnavailable
from app.modules.agent.schemas import (
    AgentSpotCard,
    AskResponse,
    ChatCardsEvent,
    ChatDeltaEvent,
    ChatDoneEvent,
    ChatErrorEvent,
    ChatRequest,
    ChatSourcesEvent,
    ChatStepEvent,
    QueryIntent,
    SourceItem,
)
from app.modules.agent.services import answer as writer_answer
from app.modules.agent.services import suggest as suggest_service
from app.modules.agent.services import writer
from app.web.errors import AppError

logger = get_logger(__name__)

BLOG_CALL_BUDGET = 4
BLOG_CALL_TIMEOUT_SECONDS = 1.8
WRITER_IDLE_TIMEOUT_SECONDS = 15.0
GROUNDED_SPOT_LIMIT = 3
GROUNDED_POST_LIMIT = 6
# 라이터는 도구 결과로 산문을 쓴다 — 후속 질문의 문맥은 context.intent/spots 가 이미 나른다.
# 이력은 직전 한 턴(user+assistant)이면 충분하고, 국외로 나가는 자유 입력을 그만큼 줄인다.
HISTORY_TAIL = 2
TOPIC_WORD_LIMIT = 4
BRACKETED = re.compile("[\\[(\uff08\u3010][^\\])\uff09\u3011]*[\\])\uff09\u3011]")
QUESTION_TAIL = re.compile(
    r"(추천\s*해?\s*줘|추천해주세요|알려\s*줘|알려주세요|찾아\s*줘|찾아주세요|"
    r"어디야|어디\s*있어|있을까|해줘|하고\s*싶어|좀|요\?|\?|!)"
)


def encode(name: str, payload: BaseModel, *, request_id: str, sequence: int) -> str:
    event_payload = payload.model_dump(mode="json")
    event_payload["requestId"] = request_id
    event_payload["sequence"] = sequence
    return f"event: {name}\ndata: {json.dumps(event_payload, ensure_ascii=False)}\n\n"


async def stream(
    session: AsyncSession,
    redis: Redis,
    kto: KtoClient | None,
    *,
    payload: ChatRequest,
    image_bytes: bytes | None,
    image_mime: str | None,
    user_id: int | None = None,
) -> AsyncIterator[str]:
    sequence = 0
    async for name, event in events(
        session,
        redis,
        kto,
        payload=payload,
        image_bytes=image_bytes,
        image_mime=image_mime,
        user_id=user_id,
    ):
        yield encode(name, event, request_id=payload.clientRequestId, sequence=sequence)
        sequence += 1


async def events(
    session: AsyncSession,
    redis: Redis,
    kto: KtoClient | None,
    *,
    payload: ChatRequest,
    image_bytes: bytes | None,
    image_mime: str | None,
    user_id: int | None = None,
) -> AsyncIterator[tuple[str, BaseModel]]:
    emitter = Emitter()
    searching = asyncio.create_task(
        _search(
            session,
            redis,
            kto,
            payload=payload,
            image_bytes=image_bytes,
            image_mime=image_mime,
            emitter=emitter,
            user_id=user_id,
        )
    )
    streamed = 0
    try:
        async for signal in emitter.drain():
            if signal.status == "done":
                streamed = max(streamed, signal.index + 1)
            yield (
                "step",
                ChatStepEvent(
                    index=signal.index,
                    label=signal.label,
                    badge=signal.badge,
                    status=signal.status,
                ),
            )
    except BaseException:
        searching.cancel()
        raise

    try:
        result = await searching
    except AppError as exc:
        logger.info("agent.chat.ask_failed", code=exc.code)
        refusal = outcome_service.classify_error(exc, blank_answer=writer_answer.BLANK_ANSWER)
        async for event in _canned(refusal.message, intent=QueryIntent(), spots=[]):
            yield event
        return

    outcome = outcome_service.classify(result)
    logger.info("agent.chat.outcome", kind=type(outcome).__name__, results=len(result.spots))

    for index in range(streamed, len(result.steps)):
        step = result.steps[index]
        yield "step", ChatStepEvent(index=index, label=step.label, status="run")
        yield "step", ChatStepEvent(index=index, label=step.label, badge=step.badge, status="done")

    applied = writer_answer.applied_conditions(result.intent, axes=suggest_service.ALL_AXES)
    if result.spots:
        yield (
            "cards",
            ChatCardsEvent(
                spots=result.spots,
                tagBasis=result.tagBasis,
                applied=applied,
                refinements=result.refinements,
            ),
        )

    if isinstance(outcome, (outcome_service.Smalltalk, outcome_service.OutOfScope)):
        async for event in _canned(
            _deterministic_answer(result) or writer_answer.BLANK_ANSWER,
            intent=result.intent,
            spots=[],
        ):
            yield event
        return

    posts = await _ground_with_blogs(result, message=payload.message)
    sources = _sources(posts)

    if (
        llm.writer_depends_on_gemini()
        and llm.structured_depends_on_gemini()
        and _llm_is_down(result)
    ):
        logger.warning("agent.chat.writer_skipped", results=len(result.spots))
        rescue = _deterministic_answer(result) or writer_answer.NO_AXIS_ANSWER
        yield "delta", ChatDeltaEvent(text=rescue)
        yield "sources", ChatSourcesEvent(items=sources)
        yield (
            "done",
            ChatDoneEvent(
                answerText=rescue,
                spots=result.spots,
                sources=sources,
                intent=result.intent,
                totalCount=result.totalCount,
                applied=applied,
                refinements=result.refinements,
                traceId=get_trace_id(),
            ),
        )
        return

    system, user_text = writer.build_prompt(
        question=(payload.message or "").strip() or None,
        intent=result.intent,
        spots=result.spots,
        blog_posts=posts,
        client_time=payload.clientTime,
        history=payload.history[-HISTORY_TAIL:],
        situation=outcome_service.situation_of(outcome),
    )
    chunks = llm.get_writer_client().stream_text(system=system, user_text=user_text)
    guarded = _watchdog(chunks)
    parts: list[str] = []
    try:
        try:
            async for written in guarded:
                parts.append(written)
                yield "delta", ChatDeltaEvent(text=written)
        except (httpx.HTTPError, llm.CodexStreamProtocolError, TimeoutError) as exc:
            logger.warning(
                "agent.chat.writer_failed",
                error_type=type(exc).__name__,
                streamed=len(parts),
            )
            if not _written(parts) and not _deterministic_answer(result):
                failure = AgentWriterUnavailable()
                yield "error", ChatErrorEvent(code=failure.code, message=failure.message)
                return
    finally:
        await _shutdown(guarded, chunks)

    answer = _written(parts)
    if not answer:
        rescue = _deterministic_answer(result)
        if not rescue:
            failure = AgentWriterUnavailable()
            yield "error", ChatErrorEvent(code=failure.code, message=failure.message)
            return
        logger.warning("agent.chat.writer_fallback", segments=len(result.answer))
        parts.append(rescue)
        answer = rescue
        yield "delta", ChatDeltaEvent(text=rescue)

    yield "sources", ChatSourcesEvent(items=sources)
    logger.info(
        "agent.chat.done",
        results=len(result.spots),
        blogs=len(posts),
    )
    yield (
        "done",
        ChatDoneEvent(
            answerText=answer,
            spots=result.spots,
            sources=sources,
            intent=result.intent,
            totalCount=result.totalCount,
            applied=applied,
            refinements=result.refinements,
            traceId=get_trace_id(),
        ),
    )


async def _canned(
    text: str, *, intent: QueryIntent, spots: list[AgentSpotCard]
) -> AsyncIterator[tuple[str, BaseModel]]:
    yield "delta", ChatDeltaEvent(text=text)
    yield (
        "done",
        ChatDoneEvent(
            answerText=text,
            spots=spots,
            sources=[],
            intent=intent,
            totalCount=len(spots),
            traceId=get_trace_id(),
        ),
    )


def _written(parts: list[str]) -> str:
    return "".join(parts).strip()


def _deterministic_answer(result: AskResponse) -> str:
    return "".join(segment.text for segment in result.answer).strip()


async def _shutdown(*iterators: AsyncIterator[object]) -> None:
    for iterator in iterators:
        aclose = getattr(iterator, "aclose", None)
        if aclose is not None:
            await aclose()


async def _watchdog(chunks: AsyncIterator[str]) -> AsyncIterator[str]:
    iterator = chunks.__aiter__()
    while True:
        try:
            chunk = await asyncio.wait_for(anext(iterator), WRITER_IDLE_TIMEOUT_SECONDS)
        except StopAsyncIteration:
            return
        yield chunk


async def _ground_with_blogs(
    result: AskResponse, *, message: str | None
) -> list[naver.NaverBlogPost]:
    probes = _blog_probes(result, message=message)
    if not probes or not naver.is_configured():
        return []
    timeout = httpx.Timeout(BLOG_CALL_TIMEOUT_SECONDS, connect=BLOG_CALL_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout) as client:
        batches = await asyncio.gather(*(_blog_call(client, probe.query) for probe in probes))
    posts: list[naver.NaverBlogPost] = []
    seen: set[str] = set()
    for probe, batch in zip(probes, batches, strict=True):
        for post in batch:
            key = post.link or post.title
            if key in seen or not _post_matches(post, probe.terms):
                continue
            seen.add(key)
            posts.append(post)
    return posts[:GROUNDED_POST_LIMIT]


@dataclass(slots=True)
class _BlogProbe:
    query: str
    terms: tuple[str, ...]


def _blog_probes(result: AskResponse, *, message: str | None) -> list[_BlogProbe]:
    probes: list[_BlogProbe] = []
    for card in result.spots[:GROUNDED_SPOT_LIMIT]:
        name = _plain_title(card.title)
        if not name:
            continue
        area = _short_region(card.regionLabel)
        query = f"{area} {name}".strip() if area else name
        probes.append(_BlogProbe(query=query, terms=(name,)))
    topic = _topic_query(message)
    if topic:
        probes.append(_BlogProbe(query=topic, terms=tuple(topic.split())))
    return probes[:BLOG_CALL_BUDGET]


def _plain_title(title: str) -> str:
    return BRACKETED.sub(" ", title).strip()


def _short_region(label: str) -> str:
    parts = [part for part in label.split() if part]
    return parts[-1] if parts else ""


def _topic_query(message: str | None) -> str:
    cleaned = QUESTION_TAIL.sub(" ", (message or "").strip())
    words = [word for word in cleaned.split() if len(word) > 1][:TOPIC_WORD_LIMIT]
    return " ".join(words)


def _post_matches(post: naver.NaverBlogPost, terms: tuple[str, ...]) -> bool:
    if not terms:
        return False
    haystack = f"{post.title} {post.description or ''}"
    return all(term in haystack for term in terms)


async def _blog_call(client: httpx.AsyncClient, query: str) -> list[naver.NaverBlogPost]:
    try:
        async with asyncio.timeout(BLOG_CALL_TIMEOUT_SECONDS):
            return await naver.search_blog(client, query)
    except (TimeoutError, httpx.HTTPError):
        logger.warning("agent.chat.blog_timeout", query=query)
        return []


def _sources(posts: list[naver.NaverBlogPost]) -> list[SourceItem]:
    return [
        SourceItem(kind="naver_blog", title=post.title, url=post.link, date=post.postdate)
        for post in posts
    ]


def _llm_is_down(result: AskResponse) -> bool:
    return any(step.badge == writer_answer.INTENT_FALLBACK_BADGE for step in result.steps)


async def _search(
    session: AsyncSession,
    redis: Redis,
    kto: KtoClient | None,
    *,
    payload: ChatRequest,
    image_bytes: bytes | None,
    image_mime: str | None,
    emitter: Emitter,
    user_id: int | None = None,
) -> AskResponse:
    """검색을 돌리고, 어떻게 끝나든 스텝 스트림을 닫는다."""
    try:
        return await search.run(
            session,
            redis,
            kto,
            question=payload.message,
            lat=payload.lat,
            lng=payload.lng,
            image_bytes=image_bytes,
            image_mime=image_mime,
            context=payload.context,
            intent=payload.intent,
            patch=payload.patch,
            emitter=emitter,
            user_id=user_id,
        )
    finally:
        emitter.close()
