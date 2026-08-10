from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx
from pydantic import BaseModel
from redis.asyncio import Redis

from app.core.db import AsyncSession
from app.core.logging import get_logger, get_trace_id
from app.kto.client import KtoClient
from app.modules.agent import llm, naver
from app.modules.agent.errors import AgentWriterUnavailable
from app.modules.agent.schemas import (
    AskResponse,
    ChatCardsEvent,
    ChatDeltaEvent,
    ChatDoneEvent,
    ChatErrorEvent,
    ChatRequest,
    ChatSourcesEvent,
    ChatStepEvent,
    ChatSuggestionsEvent,
    QueryIntent,
    SourceItem,
)
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import writer
from app.web.errors import AppError

logger = get_logger(__name__)

BLOG_CALL_BUDGET = 4
BLOG_CALL_TIMEOUT_SECONDS = 2.5
WRITER_IDLE_TIMEOUT_SECONDS = 15.0
GROUNDED_SPOT_LIMIT = 3
GROUNDED_POST_LIMIT = 6
HISTORY_TAIL = 4
KTO_SOURCE = SourceItem(
    kind="kto", title="한국관광공사 TourAPI", url="https://api.visitkorea.or.kr"
)


def encode(name: str, payload: BaseModel) -> str:
    return f"event: {name}\ndata: {payload.model_dump_json()}\n\n"


async def stream(
    session: AsyncSession,
    redis: Redis,
    kto: KtoClient | None,
    *,
    payload: ChatRequest,
    image_bytes: bytes | None,
    image_mime: str | None,
) -> AsyncIterator[str]:
    async for name, event in events(
        session, redis, kto, payload=payload, image_bytes=image_bytes, image_mime=image_mime
    ):
        yield encode(name, event)


async def events(
    session: AsyncSession,
    redis: Redis,
    kto: KtoClient | None,
    *,
    payload: ChatRequest,
    image_bytes: bytes | None,
    image_mime: str | None,
) -> AsyncIterator[tuple[str, BaseModel]]:
    try:
        result = await ask_service.ask(
            session,
            redis,
            kto,
            question=payload.message,
            lat=payload.lat,
            lng=payload.lng,
            image_bytes=image_bytes,
            image_mime=image_mime,
            context=payload.context,
        )
    except AppError as exc:
        logger.info("agent.chat.ask_failed", code=exc.code)
        yield "delta", ChatDeltaEvent(text=exc.message)
        yield (
            "done",
            ChatDoneEvent(
                answerText=exc.message,
                spots=[],
                sources=[],
                suggestions=[],
                intent=QueryIntent(),
                totalCount=0,
                traceId=get_trace_id(),
            ),
        )
        return

    for index, step in enumerate(result.steps):
        yield "step", ChatStepEvent(index=index, label=step.label, status="run")
        yield "step", ChatStepEvent(index=index, label=step.label, badge=step.badge, status="done")

    posts = await _ground_with_blogs(result, message=payload.message)
    sources = _sources(result, posts)

    system, user_text = writer.build_prompt(
        question=(payload.message or "").strip() or None,
        intent=result.intent,
        spots=result.spots,
        blog_posts=posts,
        client_time=payload.clientTime,
        history=payload.history[-HISTORY_TAIL:],
    )
    chunks = llm.get_client().stream_text(system=system, user_text=user_text)
    guarded = _watchdog(chunks)
    parsed = writer.parse_stream(guarded)
    parts: list[str] = []
    suggestions: list[str] | None = None
    cards_sent = False
    try:
        try:
            async for event in parsed:
                if isinstance(event, writer.WriterDelta):
                    parts.append(event.text)
                    yield "delta", ChatDeltaEvent(text=event.text)
                elif isinstance(event, writer.WriterCards):
                    if result.spots and not cards_sent:
                        cards_sent = True
                        yield "cards", ChatCardsEvent(spots=result.spots, tagBasis=result.tagBasis)
                else:
                    suggestions = event.items
        except Exception as exc:
            logger.warning("agent.chat.writer_failed", error_type=type(exc).__name__)
            failure = AgentWriterUnavailable()
            yield "error", ChatErrorEvent(code=failure.code, message=failure.message)
            return
    finally:
        await _shutdown(parsed, guarded, chunks)

    if result.spots and not cards_sent:
        yield "cards", ChatCardsEvent(spots=result.spots, tagBasis=result.tagBasis)
    yield "sources", ChatSourcesEvent(items=sources)
    final_suggestions = suggestions if suggestions is not None else result.suggestions
    yield "suggestions", ChatSuggestionsEvent(items=final_suggestions)
    logger.info(
        "agent.chat.done",
        results=len(result.spots),
        blogs=len(posts),
        suggested=len(final_suggestions),
    )
    yield (
        "done",
        ChatDoneEvent(
            answerText="".join(parts).strip(),
            spots=result.spots,
            sources=sources,
            suggestions=final_suggestions,
            intent=result.intent,
            totalCount=result.totalCount,
            traceId=get_trace_id(),
        ),
    )


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
    queries: list[str] = []
    for card in result.spots[:GROUNDED_SPOT_LIMIT]:
        queries.append(" ".join(part for part in (card.title, card.regionLabel) if part))
    cleaned = (message or "").strip()
    if cleaned:
        queries.append(cleaned)
    queries = queries[:BLOG_CALL_BUDGET]
    if not queries or not naver.is_configured():
        return []
    timeout = httpx.Timeout(BLOG_CALL_TIMEOUT_SECONDS, connect=BLOG_CALL_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout) as client:
        batches = await asyncio.gather(*(_blog_call(client, query) for query in queries))
    posts: list[naver.NaverBlogPost] = []
    seen: set[str] = set()
    for batch in batches:
        for post in batch:
            key = post.link or post.title
            if key in seen:
                continue
            seen.add(key)
            posts.append(post)
    return posts[:GROUNDED_POST_LIMIT]


async def _blog_call(client: httpx.AsyncClient, query: str) -> list[naver.NaverBlogPost]:
    try:
        async with asyncio.timeout(BLOG_CALL_TIMEOUT_SECONDS):
            return await naver.search_blog(client, query)
    except (TimeoutError, httpx.HTTPError):
        logger.warning("agent.chat.blog_timeout", query=query)
        return []


def _sources(result: AskResponse, posts: list[naver.NaverBlogPost]) -> list[SourceItem]:
    items = [
        SourceItem(kind="naver_blog", title=post.title, url=post.link, date=post.postdate)
        for post in posts
    ]
    if result.spots:
        items.append(KTO_SOURCE)
    return items
