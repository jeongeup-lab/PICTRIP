from __future__ import annotations

import json
import uuid
from typing import Any

from redis.asyncio import Redis

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.modules.plan import repositories
from app.modules.plan.labels import category_label
from app.modules.plan.links import place_links
from app.modules.plan.llm import generate_json, generate_turn
from app.modules.plan.naver_local import NaverPlace, search_local
from app.modules.plan.schemas import (
    ChatReply,
    ChatRequest,
    ChatResponse,
    PickCandidate,
    PickPrompt,
    PlaceCard,
    PlanPayload,
)
from app.modules.plan.services.assemble import assemble_days
from app.modules.plan.services.candidates import collect_candidates, collect_for_picks, picker_pool
from app.modules.plan.services.intent import PlanIntent, clamp_days
from app.modules.plan.services.narrate import narrate_plan
from app.modules.spots.services import (
    NearbyCategory,
    find_nearby_spots,
    load_active_spot_cards_by_ids,
    load_overview_map,
)
from app.web.errors import PlanAgentUnavailable, ResourceNotFound

logger = get_logger(__name__)

_THREAD_KEY = "plan:thread:{tid}"
_THREAD_TTL = 86_400
_MAX_THREAD_MESSAGES = 20
_MAX_CONTEXT_MESSAGES = 12

_SYSTEM = (
    "너는 PICTRIP AI, 한국 국내여행 도우미다. 반드시 '-이에요/-해요'로 끝나는 해요체로 짧게 답한다. "
    "'-습니다/-입니다'·이모지 금지. "
    "도구 규칙: "
    "1) 여행 일정(코스) 요청이면 create_plan. 목적지가 도시·시군구면 place_type=region, "
    "특정 명소·해변·역이면 place_type=spot. 기간을 모르면 days를 생략하고 호출한다. "
    "2) 특정 위치 주변의 맛집·카페·가볼 곳 추천 질문이면 recommend_places. "
    "query는 '지역명 맛집'처럼 짧게 만든다(예: '양양 현남면 맛집'). 시설 이름 전체를 넣지 않는다. "
    "3) 두 장소 사이 거리나 '얼마나 떨어져 있어' 질문이면 distance_between을 호출한다. "
    "target에는 상대 장소명을 넣는다. "
    "4) 사용자 현재 위치 기준 정렬 요청이면 nearest_matches. "
    "5) 사용자가 검색 결과를 지적하거나 다시 찾아달라고 하면 같은 검색어를 반복하지 말고 "
    "조건을 바꾼 검색어로 recommend_places를 다시 호출한다(예: '신림동 조용한 카페'). "
    "6) 영업시간·입장료·주차처럼 확인 안 된 사실은 단정하지 말고, 일반적인 경향만 말한 뒤 "
    "상세 보기나 네이버 지도 확인을 안내한다. "
    "7) 사진 매칭 목록·선택된 여행지가 컨텍스트에 있으면 그것을 기준으로 답한다. "
    "8) 일정 요청인데 지역을 모르면 어울리는 국내 지역 2~3곳을 예로 들며 짧게 되묻는다. "
    "9) 여행과 무관한 요청은 정중히 여행 얘기로 돌린다."
)

_TOOLS: list[dict[str, Any]] = [
    {
        "name": "create_plan",
        "description": "특정 지역의 여행 일정(일자별 코스)을 생성한다.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "region": {
                    "type": "STRING",
                    "description": "여행 목적지. 예: 강릉, 전주, 안목해변, 어린이대공원역",
                },
                "place_type": {
                    "type": "STRING",
                    "enum": ["region", "spot"],
                    "description": "region=도시·시군구 단위(강릉·전주), spot=특정 명소·해변·역·동네(안목해변·한옥마을)",
                },
                "days": {
                    "type": "INTEGER",
                    "description": "여행 일수 1~3. 사용자가 말했거나 명확히 유추될 때만. 모르면 생략",
                },
                "party": {"type": "STRING", "description": "동행. 예: 혼자, 커플, 부모님"},
                "mobility": {"type": "STRING", "enum": ["walk", "transit", "car"]},
                "themes": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["region"],
        },
    },
    {
        "name": "distance_between",
        "description": "선택된 여행지(또는 사용자 위치)와 특정 장소 사이의 거리를 계산해 알려준다.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target": {"type": "STRING", "description": "거리를 잴 상대 장소명. 예: 이원식당"}
            },
            "required": ["target"],
        },
    },
    {
        "name": "nearest_matches",
        "description": "사진 매칭 결과를 사용자 현재 위치에서 가까운 순으로 정렬해 보여준다.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "recommend_places",
        "description": "특정 위치 주변의 맛집·카페·가볼 곳을 단건 추천한다. 일정 생성이 아닐 때 사용.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "위치와 조건을 담은 검색어. 예: 어린이대공원역 작업하기 좋은 카페",
                }
            },
            "required": ["query"],
        },
    },
]

_FALLBACK_ASK = "어디로, 며칠 일정으로 다녀오실지 알려주시면 바로 짜드릴게요."
_ASK_DAYS = "좋아요, {region}으로 잡을게요. 며칠 일정으로 다녀오세요?"
_PICK_TEXT = (
    "{region}에서 끌리는 곳을 최대 {n}곳 골라주세요. 고른 곳을 중심으로 코스를 짤게요. "
    "고르기 귀찮으면 맡겨주셔도 돼요."
)
_AUTO_MESSAGE = "알아서 짜줘"
_ATTRACTIONS_PER_DAY = 2
_PLACES_FOUND = "네이버에서 리뷰 많은 순으로 골라봤어요."
_PLACES_FOUND_KTO = "네이버 결과가 없어서 한국관광공사 데이터에서 주변 식당을 찾았어요."
_NEAREST_FOUND = "현재 위치에서 가까운 순으로 정렬했어요."
_NEAREST_NO_LOCATION = "위치 정보를 받지 못했어요. 브라우저(앱)의 위치 권한을 허용해 주세요."
_NEAREST_NO_MATCHES = "먼저 사진을 올려서 닮은 여행지를 찾아볼까요?"
_SPOT_INTRO_FALLBACK = "{name} — {category}. 카드를 눌러 자세히 볼 수 있어요."
_PLACES_EMPTY = "마땅한 곳을 찾지 못했어요. 위치나 조건을 조금 바꿔서 다시 말해줄래요?"


async def load_thread_state(redis: Redis, tid: str) -> dict[str, Any]:
    try:
        raw = await redis.get(_THREAD_KEY.format(tid=tid))
    except Exception as exc:
        logger.warning("plan.thread.load_failed", error=str(exc))
        return {}
    if not raw:
        return {}
    try:
        text = raw.decode() if isinstance(raw, bytes) else raw
        state = json.loads(text)
    except (ValueError, TypeError) as exc:
        logger.warning("plan.thread.corrupt", error=str(exc))
        return {}
    return state if isinstance(state, dict) else {}


async def save_thread_state(redis: Redis, tid: str, state: dict[str, Any]) -> None:
    try:
        await redis.set(_THREAD_KEY.format(tid=tid), json.dumps(state), ex=_THREAD_TTL)
    except Exception as exc:
        logger.warning("plan.thread.save_failed", error=str(exc))


def _normalize_messages(raw: Any) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return messages
    for item in raw:
        if isinstance(item, dict) and item.get("role") in ("user", "model") and item.get("text"):
            messages.append({"role": str(item["role"]), "text": str(item["text"])})
        elif isinstance(item, str):
            messages.append({"role": "user", "text": item})
    return messages


async def _generate(
    session: AsyncSession,
    *,
    tid: str,
    user_id: int | None,
    intent: PlanIntent,
    picked_ids: list[str] | None = None,
) -> tuple[PlanPayload, str]:
    if picked_ids:
        cand = await collect_for_picks(session, intent, picked_ids)
    else:
        cand = await collect_candidates(session, intent)
    days = await assemble_days(intent, cand)
    texts = await narrate_plan(intent, days)
    plan_id = uuid.uuid4()
    payload = PlanPayload(
        planId=str(plan_id),
        title=texts["title"],
        summary=texts["summary"],
        region=intent.region or "",
        days=days,
    )
    await repositories.insert_plan(
        session,
        plan_id=plan_id,
        thread_id=tid,
        user_id=user_id,
        payload=payload.model_dump(),
    )
    return payload, texts["replyText"]


def _intent_from_args(args: dict[str, Any]) -> PlanIntent | None:
    region = str(args.get("region") or "").strip()
    if not region:
        return None
    mobility = args.get("mobility")
    themes = args.get("themes")
    party = args.get("party")
    return PlanIntent(
        region=region,
        days=clamp_days(args.get("days")),
        party=str(party).strip() or None if isinstance(party, str) else None,
        themes=[str(t) for t in themes if str(t).strip()] if isinstance(themes, list) else [],
        mobility=mobility if mobility in ("walk", "transit", "car") else None,
    )


def _match_dist_km(m: dict[str, Any], lat: float, lng: float) -> float:
    import math

    mlat, mlng = m.get("lat"), m.get("lng")
    if mlat is None or mlng is None:
        return 1e9
    p1, p2 = math.radians(lat), math.radians(float(mlat))
    dp = math.radians(float(mlat) - lat)
    dl = math.radians(float(mlng) - lng)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def _match_to_place(m: dict[str, Any]) -> PlaceCard:
    return PlaceCard(
        name=str(m.get("name") or ""),
        contentId=m.get("contentId"),
        category=m.get("category"),
        address=m.get("address"),
        lat=m.get("lat"),
        lng=m.get("lng"),
        imageUrl=m.get("imageUrl"),
        links=place_links(str(m.get("name") or ""), m.get("lat"), m.get("lng")),
    )


def _nearest_matches_reply(state: dict[str, Any], req: ChatRequest) -> ChatReply:
    matches = state.get("matches") or []
    if not matches:
        return ChatReply(type="text", text=_NEAREST_NO_MATCHES)
    if req.location is None:
        return ChatReply(type="text", text=_NEAREST_NO_LOCATION)
    ordered = sorted(matches, key=lambda m: _match_dist_km(m, req.location.lat, req.location.lng))
    return ChatReply(
        type="places",
        text=_NEAREST_FOUND,
        places=[_match_to_place(m) for m in ordered[:6]],
    )


async def _select_spot_reply(
    session: AsyncSession, state: dict[str, Any], content_id: str
) -> ChatReply:
    cards = await load_active_spot_cards_by_ids(session, [content_id])
    card = cards.get(content_id)
    if card is None:
        return ChatReply(type="text", text="해당 여행지를 찾지 못했어요.")
    name = str(getattr(card, "title", ""))
    category = (
        getattr(card, "lcls_systm3_nm", None)
        or category_label(getattr(card, "category", None))
        or "여행지"
    )
    addr = getattr(card, "addr1", None)
    place = PlaceCard(
        name=name,
        contentId=content_id,
        category=category,
        address=addr,
        lat=getattr(card, "mapy", None),
        lng=getattr(card, "mapx", None),
        imageUrl=getattr(card, "first_image_url", None),
        links=place_links(name, getattr(card, "mapy", None), getattr(card, "mapx", None)),
    )
    overview_map = await load_overview_map(session, [content_id])
    overview = (overview_map.get(content_id) or "")[:400]
    intro_raw = await generate_json(
        system=(
            "너는 한국 국내여행 도우미다. 주어진 여행지 정보로 2~3문장 소개를 쓴다. "
            "반드시 '-이에요/-해요'로 끝나는 해요체. '-습니다/-입니다'·이모지 금지. "
            "공식 설명이 있으면 그 내용을 근거로 핵심만 자기 문장으로 풀어 쓰고, "
            "공식 설명에 없는 구체 정보(영업시간·요금 등)는 지어내지 않는다. JSON으로만 답한다."
        ),
        user=f"이름: {name}\n분류: {category}\n주소: {addr}\n공식 설명: {overview or '없음'}",
        schema={
            "type": "OBJECT",
            "properties": {"intro": {"type": "STRING"}},
            "required": ["intro"],
        },
        temperature=0.6,
    )
    intro = (
        str(intro_raw.get("intro"))
        if intro_raw and intro_raw.get("intro")
        else _SPOT_INTRO_FALLBACK.format(name=name, category=category)
    )
    state["selected"] = {
        "contentId": content_id,
        "name": name,
        "address": addr,
        "lat": getattr(card, "mapy", None),
        "lng": getattr(card, "mapx", None),
    }
    return ChatReply(type="spot", text=intro, spot=place)


_FOOD_KEYWORDS = ("맛집", "밥집", "카페", "술집", "빵집", "식당", "삼겹살")
_CAFE_INCLUDE = ("카페", "커피", "디저트", "베이커리", "찻집")
_FOOD_INCLUDE = (
    "음식점",
    "한식",
    "일식",
    "중식",
    "양식",
    "분식",
    "뷔페",
    "아시아",
    "해물",
    "생선",
    "육류",
    "고기",
    "치킨",
    "피자",
    "패스트푸드",
    "술집",
    "호프",
    "요리",
)


def _category_ok(keyword: str | None, category: str | None) -> bool:
    if keyword is None:
        return True
    cat = category or ""
    if keyword == "카페":
        return any(k in cat for k in _CAFE_INCLUDE)
    if keyword == "빵집":
        return any(k in cat for k in ("베이커리", "빵", "디저트", "카페"))
    return any(k in cat for k in _FOOD_INCLUDE)


def _context_anchor(state: dict[str, Any]) -> tuple[float, float, str | None] | None:
    selected = state.get("selected")
    if isinstance(selected, dict) and selected.get("lat") and selected.get("lng"):
        return float(selected["lat"]), float(selected["lng"]), selected.get("address")
    for m in state.get("matches") or []:
        if m.get("lat") and m.get("lng"):
            return float(m["lat"]), float(m["lng"]), m.get("address")
    return None


def _locality_of(address: str | None) -> str | None:
    if not address:
        return None
    parts = str(address).split()
    if len(parts) < 2:
        return None
    sido = parts[0]
    for suffix in ("특별자치도", "특별자치시", "특별시", "광역시", "도"):
        if sido.endswith(suffix):
            sido = sido[: -len(suffix)]
            break
    return f"{sido} {parts[1]}"


async def _recommend_places(session: AsyncSession, state: dict[str, Any], query: str) -> ChatReply:
    keyword = next((k for k in _FOOD_KEYWORDS if k in query), None)
    anchor = _context_anchor(state)

    last = state.get("lastReco") or {}
    exclude: set[str] = (
        set(last.get("names") or []) if last.get("keyword") == (keyword or query) else set()
    )

    def usable(raw: list[NaverPlace]) -> list[NaverPlace]:
        ok = [p for p in raw if _category_ok(keyword, p.category)]
        fresh = [p for p in ok if p.name not in exclude]
        return fresh or ok

    places = usable(await search_local(query, display=5))
    if not places and anchor and anchor[2]:
        locality = _locality_of(anchor[2])
        retry_term = keyword or (query.split()[-1] if len(query.split()) > 1 else query)
        if locality and locality not in query:
            places = usable(await search_local(f"{locality} {retry_term}", display=5))

    cards = [
        PlaceCard(
            name=p.name,
            source="naver",
            category=p.category,
            address=p.address,
            lat=p.lat,
            lng=p.lng,
            links=place_links(p.name, p.lat, p.lng),
        )
        for p in places
    ]

    if not cards and anchor and keyword is not None:
        category = NearbyCategory.cafe if keyword == "카페" else NearbyCategory.food
        rows = await find_nearby_spots(
            session, lat=anchor[0], lng=anchor[1], radius=8_000, category=category
        )
        cards = [
            PlaceCard(
                name=r.title,
                source="kto",
                contentId=r.content_id,
                category=category_label("cafe" if category is NearbyCategory.cafe else "food"),
                address=r.addr1,
                lat=r.mapy,
                lng=r.mapx,
                imageUrl=r.first_image_url,
                links=place_links(r.title, r.mapy, r.mapx),
            )
            for r in rows[:5]
        ]

    if not cards:
        return ChatReply(type="text", text=_PLACES_EMPTY)

    state["places"] = [
        {
            "name": c.name,
            "lat": c.lat,
            "lng": c.lng,
            "address": c.address,
        }
        for c in cards
    ]
    state["lastReco"] = {"keyword": keyword or query, "names": [c.name for c in cards]}
    text = _PLACES_FOUND if cards[0].source == "naver" else _PLACES_FOUND_KTO
    return ChatReply(type="places", text=text, places=cards)


def _km_between(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math

    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def _distance_reply(state: dict[str, Any], req: ChatRequest, target: str) -> ChatReply:
    from difflib import SequenceMatcher

    def ratio(a: str, b: str) -> float:
        return SequenceMatcher(None, a.replace(" ", ""), b.replace(" ", "")).ratio()

    pool: list[dict[str, Any]] = []
    pool.extend(state.get("places") or [])
    pool.extend(state.get("matches") or [])
    best = None
    for item in pool:
        name = str(item.get("name") or "")
        if not name or item.get("lat") is None or item.get("lng") is None:
            continue
        r = ratio(target, name)
        if r >= 0.45 and (best is None or r > best[0]):
            best = (r, item)
    if best is None:
        return ChatReply(type="text", text=f"'{target}'의 위치 정보를 찾지 못했어요.")

    item = best[1]
    selected = state.get("selected")
    if isinstance(selected, dict) and selected.get("lat") and selected.get("lng"):
        origin_name = str(selected.get("name"))
        km = _km_between(
            float(selected["lat"]),
            float(selected["lng"]),
            float(item["lat"]),
            float(item["lng"]),
        )
    elif req.location is not None:
        origin_name = "현재 위치"
        km = _km_between(req.location.lat, req.location.lng, float(item["lat"]), float(item["lng"]))
    else:
        return ChatReply(type="text", text=_NEAREST_NO_LOCATION)

    drive_min = max(3, round(km / 40 * 60))
    if km < 1.5:
        walk_min = max(2, round(km * 1000 / 67))
        text = f"{origin_name}에서 {item['name']}까지 직선거리 약 {km:.1f}km, 걸어서 {walk_min}분쯤이에요."
    else:
        text = f"{origin_name}에서 {item['name']}까지 직선거리 약 {km:.1f}km, 차로 {drive_min}분쯤이에요."
    return ChatReply(type="text", text=text)


async def handle_chat(
    session: AsyncSession,
    redis: Redis,
    *,
    req: ChatRequest,
    user_id: int | None,
) -> ChatResponse:
    tid = req.threadId or uuid.uuid4().hex
    state = await load_thread_state(redis, tid)
    messages = _normalize_messages(state.get("messages"))[-_MAX_THREAD_MESSAGES:]
    messages.append({"role": "user", "text": req.message})

    if req.selectId:
        reply = await _select_spot_reply(session, state, req.selectId)
        messages.append({"role": "model", "text": reply.text})
        state["messages"] = messages[-_MAX_THREAD_MESSAGES:]
        await save_thread_state(redis, tid, state)
        return ChatResponse(threadId=tid, reply=reply)

    pending = state.get("pendingIntent")
    picks = [str(x) for x in (req.picks or []) if str(x).strip()]
    if isinstance(pending, dict) and (picks or req.message.strip() == _AUTO_MESSAGE):
        pending_intent = PlanIntent(
            region=str(pending.get("region") or "") or None,
            days=clamp_days(pending.get("days")) or 1,
            party=pending.get("party"),
            themes=pending.get("themes") or [],
            mobility=pending.get("mobility"),
        )
        payload, reply_text = await _generate(
            session, tid=tid, user_id=user_id, intent=pending_intent, picked_ids=picks or None
        )
        state.pop("pendingIntent", None)
        state["planId"] = payload.planId
        reply = ChatReply(type="plan", text=reply_text, plan=payload)
        messages.append({"role": "model", "text": reply.text})
        state["messages"] = messages[-_MAX_THREAD_MESSAGES:]
        await save_thread_state(redis, tid, state)
        return ChatResponse(threadId=tid, reply=reply)

    contents = [
        {"role": m["role"], "parts": [{"text": m["text"]}]}
        for m in messages[-_MAX_CONTEXT_MESSAGES:]
    ]
    system = _SYSTEM
    matches = state.get("matches") or []
    if matches:
        names = ", ".join(str(m.get("name")) for m in matches[:12])
        system += f" [컨텍스트] 사진 매칭 여행지 목록: {names}."
    selected = state.get("selected")
    if isinstance(selected, dict) and selected.get("name"):
        system += f" [컨텍스트] 선택된 여행지: {selected['name']}({selected.get('address') or ''})."
    turn = await generate_turn(system=system, contents=contents, tools=_TOOLS)
    if turn is None:
        raise PlanAgentUnavailable()

    if turn.call_name == "create_plan":
        intent = _intent_from_args(turn.call_args or {})
        if intent is None:
            reply = ChatReply(type="text", text=_FALLBACK_ASK)
        elif intent.days is None:
            reply = ChatReply(
                type="text",
                text=_ASK_DAYS.format(region=intent.region),
                chips=["당일치기", "1박 2일", "2박 3일"],
            )
        elif (turn.call_args or {}).get("place_type") == "spot":
            payload, reply_text = await _generate(session, tid=tid, user_id=user_id, intent=intent)
            state["planId"] = payload.planId
            reply = ChatReply(type="plan", text=reply_text, plan=payload)
        else:
            pool = await picker_pool(session, intent)
            spots = [
                PickCandidate(
                    contentId=r.content_id,
                    name=r.title,
                    category=r.category,
                    imageUrl=r.first_image_url or "",
                )
                for r in pool
                if r.first_image_url
            ]
            if len(spots) < 4:
                payload, reply_text = await _generate(
                    session, tid=tid, user_id=user_id, intent=intent
                )
                state["planId"] = payload.planId
                reply = ChatReply(type="plan", text=reply_text, plan=payload)
            else:
                max_picks = (intent.days or 1) * _ATTRACTIONS_PER_DAY
                state["pendingIntent"] = intent.to_dict()
                reply = ChatReply(
                    type="pick",
                    text=_PICK_TEXT.format(region=intent.region, n=max_picks),
                    chips=[_AUTO_MESSAGE],
                    pick=PickPrompt(maxPicks=max_picks, spots=spots),
                )
    elif turn.call_name == "nearest_matches":
        reply = _nearest_matches_reply(state, req)
    elif turn.call_name == "recommend_places":
        query = str((turn.call_args or {}).get("query") or req.message).strip()
        reply = await _recommend_places(session, state, query)
    elif turn.call_name == "distance_between":
        target = str((turn.call_args or {}).get("target") or "").strip()
        reply = (
            _distance_reply(state, req, target)
            if target
            else ChatReply(type="text", text="어느 장소와의 거리인지 알려줄래요?")
        )
    else:
        reply = ChatReply(type="text", text=turn.text or _FALLBACK_ASK)

    messages.append({"role": "model", "text": reply.text})
    state["messages"] = messages[-_MAX_THREAD_MESSAGES:]
    await save_thread_state(redis, tid, state)
    return ChatResponse(threadId=tid, reply=reply)


async def get_plan_payload(session: AsyncSession, plan_id: uuid.UUID) -> dict[str, Any]:
    row = await repositories.get_plan(session, plan_id)
    if row is None:
        raise ResourceNotFound()
    return dict(row.payload)
