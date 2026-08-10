from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass

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
    QueryIntent,
    SourceItem,
)
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import writer
from app.web.errors import AppError, ValidationFailed

logger = get_logger(__name__)

BLOG_CALL_BUDGET = 4
BLOG_CALL_TIMEOUT_SECONDS = 1.8
WRITER_IDLE_TIMEOUT_SECONDS = 15.0
GROUNDED_SPOT_LIMIT = 3
GROUNDED_POST_LIMIT = 6
HISTORY_TAIL = 4
TOPIC_WORD_LIMIT = 4
BRACKETED = re.compile("[\\[(\uff08\u3010][^\\])\uff09\u3011]*[\\])\uff09\u3011]")
QUESTION_TAIL = re.compile(
    r"(추천\s*해?\s*줘|추천해주세요|알려\s*줘|알려주세요|찾아\s*줘|찾아주세요|"
    r"어디야|어디\s*있어|있을까|해줘|하고\s*싶어|좀|요\?|\?|!)"
)
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
        guidance = ask_service.BLANK_ANSWER if isinstance(exc, ValidationFailed) else exc.message
        yield "delta", ChatDeltaEvent(text=guidance)
        yield (
            "done",
            ChatDoneEvent(
                answerText=guidance,
                spots=[],
                sources=[],
                intent=QueryIntent(),
                totalCount=0,
                traceId=get_trace_id(),
            ),
        )
        return

    for index, step in enumerate(result.steps):
        yield "step", ChatStepEvent(index=index, label=step.label, status="run")
        yield "step", ChatStepEvent(index=index, label=step.label, badge=step.badge, status="done")

    if result.spots:
        yield "cards", ChatCardsEvent(spots=result.spots, tagBasis=result.tagBasis)

    posts = await _ground_with_blogs(result, message=payload.message)
    sources = _sources(result, posts)

    if _llm_is_down(result):
        logger.warning("agent.chat.writer_skipped", results=len(result.spots))
        rescue = _deterministic_answer(result) or ask_service.NO_AXIS_ANSWER
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
    )
    chunks = llm.get_client().stream_text(system=system, user_text=user_text)
    guarded = _watchdog(chunks)
    parsed = writer.parse_stream(guarded)
    parts: list[str] = []
    try:
        try:
            async for event in parsed:
                if isinstance(event, writer.WriterDelta):
                    parts.append(event.text)
                    yield "delta", ChatDeltaEvent(text=event.text)
        except Exception as exc:
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
        await _shutdown(parsed, guarded, chunks)

    if not _written(parts) and (rescue := _deterministic_answer(result)):
        logger.warning("agent.chat.writer_fallback", segments=len(result.answer))
        parts.append(rescue)
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
            answerText=_written(parts),
            spots=result.spots,
            sources=sources,
            intent=result.intent,
            totalCount=result.totalCount,
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


def _sources(result: AskResponse, posts: list[naver.NaverBlogPost]) -> list[SourceItem]:
    items = [
        SourceItem(kind="naver_blog", title=post.title, url=post.link, date=post.postdate)
        for post in posts
    ]
    if result.spots:
        items.append(KTO_SOURCE)
    return items


def _llm_is_down(result: AskResponse) -> bool:
    return any(step.badge == ask_service.INTENT_FALLBACK_BADGE for step in result.steps)
