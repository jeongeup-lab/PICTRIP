"""CHT services — turn orchestration: apply -> discover -> compose -> board.

The board's next question comes from a deterministic axis ladder (not the LLM):
each answer maps to a real filter the discover query understands, so the 스무고개
never asks something it cannot honor. Time-of-day answers are keyword filters over
title/overview (the concentration table is an aggregate rate, not hourly).
"""

from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.chat.llm import ChatLLM, build_chat_llm
from app.modules.chat.schemas import (
    ChatAnswer,
    ChatCard,
    ChatCondition,
    ChatTurnRequest,
    ChatTurnResponse,
)
from app.modules.chat.state import ChatSession, Condition, load_session, new_session, save_session
from app.modules.spots.services.discover import (
    DiscoverFilters,
    discover_spots,
    pool_total,
    resolve_region,
)
from app.modules.spots.services.nearby import NearbyCategory

_MAX_KEYWORDS = 4

_CATEGORY_LABELS = {
    "attraction": "관광지",
    "food": "맛집",
    "cafe": "카페",
    "leisure": "레저",
    "shopping": "쇼핑",
}

# axis_id, question, [(answer label, utterance | None=skip)]
_AXES: list[tuple[str, str, list[tuple[str, str | None]]]] = [
    (
        "category",
        "어떤 곳을 찾으세요?",
        [
            ("카페", "카페"),
            ("맛집", "맛집"),
            ("관광지", "관광지"),
            ("자연·산책", "숲 공원 산책"),
            ("상관없어요", None),
        ],
    ),
    (
        "quiet",
        "사람 붐비는 건 어떠세요?",
        [("한적한 곳이 좋아요", "한적한"), ("괜찮아요", None)],
    ),
    (
        "scenery",
        "어떤 풍경이 끌리세요?",
        [
            ("바다·물가", "바다 호수"),
            ("숲·산", "숲 산"),
            ("골목·거리", "골목 거리"),
            ("상관없어요", None),
        ],
    ),
    (
        "timing",
        "언제의 느낌이 좋으세요?",
        [("노을·해질녘", "노을"), ("아침·일출", "일출"), ("상관없어요", None)],
    ),
]


def _cat_label(code: str) -> str:
    return _CATEGORY_LABELS.get(code, code)


async def _apply_utterance(
    db: AsyncSession, session: ChatSession, utterance: str, llm: ChatLLM
) -> None:
    extracted = await llm.extract(utterance, session.conditions)
    for name in extracted.region_names:
        hit = await resolve_region(db, name)
        if hit is None:
            continue
        region_cd, sigungu_cd, label = hit
        session.conditions = [c for c in session.conditions if c.kind != "region"]
        session.conditions.append(
            Condition(
                id=f"region:{sigungu_cd or region_cd}",
                kind="region",
                label=label,
                region_cd=region_cd,
                sigungu_cd=sigungu_cd,
            )
        )
        extracted.keywords = [k for k in extracted.keywords if k != name]
        break
    existing = {c.id for c in session.conditions}
    for cat in extracted.categories:
        cid = f"category:{cat}"
        session.conditions = [c for c in session.conditions if c.id != f"exclude:{cat}"]
        if cid not in existing:
            session.conditions.append(
                Condition(id=cid, kind="category", label=_cat_label(cat), category=cat)
            )
    for cat in extracted.exclude_categories:
        cid = f"exclude:{cat}"
        session.conditions = [c for c in session.conditions if c.id != f"category:{cat}"]
        if cid not in existing:
            session.conditions.append(
                Condition(
                    id=cid,
                    kind="exclude_category",
                    label=f"{_cat_label(cat)} 제외",
                    category=cat,
                    exclude=True,
                )
            )
    if extracted.quiet and "quiet" not in existing:
        session.conditions.append(Condition(id="quiet", kind="quiet", label="한적한"))
    for kw in extracted.keywords:
        cid = f"kw:{kw}"
        if cid in {c.id for c in session.conditions}:
            continue
        session.conditions.append(Condition(id=cid, kind="keyword", label=kw, keyword=kw))
    keywords = [c for c in session.conditions if c.kind == "keyword"]
    for stale in keywords[:-_MAX_KEYWORDS]:
        session.conditions.remove(stale)


def _to_filters(session: ChatSession) -> DiscoverFilters:
    region = next((c for c in session.conditions if c.kind == "region"), None)
    return DiscoverFilters(
        region_cd=region.region_cd if region else None,
        sigungu_cd=region.sigungu_cd if region else None,
        categories=tuple(
            NearbyCategory(c.category)
            for c in session.conditions
            if c.kind == "category" and c.category
        ),
        exclude_categories=tuple(
            NearbyCategory(c.category)
            for c in session.conditions
            if c.kind == "exclude_category" and c.category
        ),
        keywords=tuple(c.keyword for c in session.conditions if c.kind == "keyword" and c.keyword),
        quiet=any(c.kind == "quiet" for c in session.conditions),
    )


def _has_category(session: ChatSession) -> bool:
    return any(c.kind in ("category", "exclude_category") for c in session.conditions)


def _next_axis(session: ChatSession) -> tuple[str, str, list[tuple[str, str | None]]] | None:
    for axis_id, question, answers in _AXES:
        if axis_id in session.asked_axes:
            continue
        if axis_id == "category" and _has_category(session):
            continue
        return axis_id, question, answers
    return None


def _axis_answers(axis_id: str, answers: list[tuple[str, str | None]]) -> list[ChatAnswer]:
    out: list[ChatAnswer] = []
    for i, (label, utterance) in enumerate(answers):
        if utterance is None:
            out.append(ChatAnswer(id=f"{axis_id}:skip:{i}", label=label, kind="skip"))
        else:
            out.append(
                ChatAnswer(id=f"{axis_id}:{i}", label=label, kind="ask", utterance=utterance)
            )
    return out


def _converge_board(count: int) -> tuple[str, list[ChatAnswer]]:
    question = "이 곳으로 정할까요?" if count <= 1 else f"이 {count}곳으로 정할까요?"
    answers = [
        ChatAnswer(id="commit", label="이대로 확정", kind="commit"),
        ChatAnswer(id="refine", label="조금 더 좁힐래요", kind="skip"),
        ChatAnswer(id="restart", label="다른 결로 다시", kind="restart"),
    ]
    return question, answers


def _empty_board(session: ChatSession) -> tuple[str, list[ChatAnswer]]:
    droppable = list(session.conditions)[-3:]
    answers = [
        ChatAnswer(
            id=f"drop:{c.id}", label=f"{c.label} 제거", kind="remove", removeConditionId=c.id
        )
        for c in reversed(droppable)
    ]
    answers.append(ChatAnswer(id="restart", label="다른 결로 다시", kind="restart"))
    return "어떤 조건을 제거할까요?", answers


async def run_turn(
    session_db: AsyncSession,
    redis: Redis,
    req: ChatTurnRequest,
    llm: ChatLLM | None = None,
) -> ChatTurnResponse:
    llm = llm or build_chat_llm()
    chat = (await load_session(redis, req.sessionId)) if req.sessionId else None
    if chat is None:
        chat = new_session()

    if req.removeConditionId:
        chat.conditions = [c for c in chat.conditions if c.id != req.removeConditionId]
    if req.utterance:
        await _apply_utterance(session_db, chat, req.utterance, llm)

    total_pool = await pool_total(session_db)
    rows, count = await discover_spots(
        session_db, filters=_to_filters(chat), limit=settings.CHAT_CANDIDATE_CARDS
    )
    composed = await llm.compose(chat.conditions, rows, count)
    chat.turns += 1

    converged = 0 < count <= settings.CHAT_CONVERGE_AT and chat.turns >= 2
    if count == 0:
        phase = "empty"
        bot_text = "이 조건까지 얹으니 남는 곳이 없네요."
        question, answers = _empty_board(chat)
    elif converged:
        phase = "converged"
        bot_text = composed.bot_text
        question, answers = _converge_board(count)
    else:
        phase = "refining"
        bot_text = composed.bot_text
        axis = _next_axis(chat)
        if axis is None:
            question = (
                "마음에 드는 곳이 있으면 눌러서 상세로 가세요. 더 좁히려면 자유롭게 적어주세요."
            )
            answers = [
                ChatAnswer(id="commit", label="이대로 좋아요", kind="commit"),
                ChatAnswer(id="restart", label="다른 결로 다시", kind="restart"),
            ]
        else:
            axis_id, question, raw_answers = axis
            chat.asked_axes.append(axis_id)
            answers = _axis_answers(axis_id, raw_answers)

    await save_session(redis, chat)

    return ChatTurnResponse(
        sessionId=chat.session_id,
        round=chat.turns + 1,
        phase=phase,
        poolTotal=total_pool,
        candidateCount=count,
        conditions=[
            ChatCondition(id=c.id, label=c.label, exclude=c.exclude) for c in chat.conditions
        ],
        botText=bot_text,
        cards=[
            ChatCard(
                contentId=r.content_id,
                title=r.title,
                firstImageUrl=r.first_image_url,
                category=r.category,
                regionLabel=r.region_label,
                why=composed.whys.get(r.content_id, ""),
                quiet=r.quiet,
            )
            for r in rows
        ],
        question=question,
        answers=answers,
    )


async def mood_covers(
    session_db: AsyncSession,
    utterances: list[str],
    llm: ChatLLM | None = None,
) -> list[tuple[str, str | None]]:
    llm = llm or build_chat_llm()
    out: list[tuple[str, str | None]] = []
    for utterance in utterances:
        chat = new_session()
        await _apply_utterance(session_db, chat, utterance, llm)
        rows, _ = await discover_spots(session_db, filters=_to_filters(chat), limit=1)
        out.append((utterance, rows[0].first_image_url if rows else None))
    return out
