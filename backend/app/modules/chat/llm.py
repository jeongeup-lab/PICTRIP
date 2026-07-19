"""CHT LLM seam — Anthropic when keyed, deterministic heuristic otherwise (tests/demo).

The seam has two jobs: translate a Korean utterance into structured filters
(extract) and write the warm grounded reaction line + per-card rationale
(compose). The board's next question is NOT the LLM's job — the service builds it
from a deterministic axis ladder so every answer maps to a real filter.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import settings
from app.modules.chat.state import Condition
from app.modules.spots.services.discover import DiscoverRow


@dataclass
class ExtractResult:
    region_names: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    exclude_categories: list[str] = field(default_factory=list)
    quiet: bool = False
    keywords: list[str] = field(default_factory=list)


@dataclass
class ComposeResult:
    bot_text: str
    whys: dict[str, str]


class ChatLLM(Protocol):
    async def extract(self, utterance: str, conditions: list[Condition]) -> ExtractResult: ...

    async def compose(
        self, conditions: list[Condition], rows: list[DiscoverRow], total: int
    ) -> ComposeResult: ...


_CATEGORY_WORDS = {
    "cafe": ("카페", "커피", "찻집"),
    "food": ("맛집", "식당", "음식점", "먹거리"),
    "attraction": ("관광지", "명소", "볼거리", "유적"),
    "leisure": ("레저", "액티비티", "체험"),
    "shopping": ("쇼핑", "시장", "장터"),
}
_QUIET_WORDS = ("한적", "조용", "붐비지", "여유", "한산")
_EXCLUDE_MARKERS = ("말고", "빼고", "제외", "싫", "아니")
_STOPWORDS = {
    "쪽으로",
    "쪽",
    "느낌",
    "근처",
    "주변",
    "데가",
    "데",
    "곳",
    "좋겠어",
    "좋은",
    "가고",
    "싶어",
    "볼래",
    "보여줘",
    "추천",
    "해줘",
    "있는",
    "그런",
    "좀",
    "더",
    "그냥",
    "낫겠어",
    "같아요",
    "정말",
}


class HeuristicChatLLM:
    async def extract(self, utterance: str, conditions: list[Condition]) -> ExtractResult:
        out = ExtractResult()
        text = utterance.strip()
        has_exclusion = any(m in text for m in _EXCLUDE_MARKERS)
        for code, words in _CATEGORY_WORDS.items():
            for w in words:
                if w in text:
                    idx = text.index(w)
                    tail = text[idx : idx + len(w) + 4]
                    if has_exclusion and any(m in tail for m in _EXCLUDE_MARKERS):
                        out.exclude_categories.append(code)
                    else:
                        out.categories.append(code)
                    break
        out.quiet = any(w in text for w in _QUIET_WORDS)
        known = {w for ws in _CATEGORY_WORDS.values() for w in ws}
        for tok in re.split(r"[\s,]+", text):
            t = tok.strip("~!?.,·")
            if len(t) < 2 or t in _STOPWORDS or t in known:
                continue
            if any(m in t for m in _EXCLUDE_MARKERS) or any(w in t for w in _QUIET_WORDS):
                continue
            out.region_names.append(t)
            out.keywords.append(t)
        return out

    async def compose(
        self, conditions: list[Condition], rows: list[DiscoverRow], total: int
    ) -> ComposeResult:
        whys: dict[str, str] = {}
        for r in rows:
            parts = [p for p in (r.category, r.region_label or None) if p]
            if r.quiet:
                parts.append("지금 한산")
            whys[r.content_id] = " · ".join(parts) if parts else "조건과 결이 맞는 곳"
        return ComposeResult(
            bot_text=f"조건에 맞는 곳이 {total}곳 남았어요. 결이 맞는 순서로 골라봤어요.",
            whys=whys,
        )


_EXTRACT_TOOL = {
    "name": "set_conditions",
    "description": "Translate the Korean utterance into structured travel filters.",
    "input_schema": {
        "type": "object",
        "properties": {
            "region_names": {"type": "array", "items": {"type": "string"}},
            "categories": {
                "type": "array",
                "items": {"enum": ["attraction", "food", "cafe", "leisure", "shopping"]},
            },
            "exclude_categories": {
                "type": "array",
                "items": {"enum": ["attraction", "food", "cafe", "leisure", "shopping"]},
            },
            "quiet": {"type": "boolean"},
            "keywords": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["region_names", "categories", "exclude_categories", "quiet", "keywords"],
    },
}

_COMPOSE_TOOL = {
    "name": "compose_reply",
    "description": "Write the grounded Korean guide reply and per-card rationale.",
    "input_schema": {
        "type": "object",
        "properties": {
            "bot_text": {"type": "string"},
            "whys": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "contentId": {"type": "string"},
                        "why": {"type": "string"},
                    },
                    "required": ["contentId", "why"],
                },
            },
        },
        "required": ["bot_text", "whys"],
    },
}

_GUARDRAIL = (
    "너는 PicTrip의 여행 스팟 발견 도우미 '픽트립'이다. 따뜻하고 담백한 동행자 말투로, "
    "제공된 데이터 밖의 사실(가격, 운영시간, 예약, 날씨)은 절대 말하지 않는다. 스팟 설명 "
    "원문을 재작성하지 않는다. 여행 스팟 찾기 외의 요청은 정중히 여행 이야기로 되돌린다. "
    "한국어로, 두 문장 이내로 답한다."
)


class AnthropicChatLLM:
    def __init__(self) -> None:
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._fallback = HeuristicChatLLM()

    async def _tool_call(self, prompt: str, tool: dict[str, Any]) -> dict[str, Any] | None:
        try:
            msg = await self._client.messages.create(  # type: ignore[call-overload]
                model=settings.CHAT_MODEL,
                max_tokens=700,
                system=_GUARDRAIL,
                messages=[{"role": "user", "content": prompt}],
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
            )
        except Exception:
            return None
        for block in msg.content:
            if getattr(block, "type", None) == "tool_use":
                data = getattr(block, "input", None)
                return data if isinstance(data, dict) else None
        return None

    async def extract(self, utterance: str, conditions: list[Condition]) -> ExtractResult:
        cond_desc = ", ".join(f"{c.kind}:{c.label}" for c in conditions) or "없음"
        data = await self._tool_call(
            f"현재 누적 조건: {cond_desc}\n사용자 발화: {utterance}\n"
            "발화를 조건으로 번역하라. 지역명은 region_names에, 분위기/활동/풍경 단어는 "
            "keywords에 짧은 명사로 넣어라. 한적함 요구는 quiet=true.",
            _EXTRACT_TOOL,
        )
        if data is None:
            return await self._fallback.extract(utterance, conditions)
        return ExtractResult(
            region_names=list(data.get("region_names", [])),
            categories=list(data.get("categories", [])),
            exclude_categories=list(data.get("exclude_categories", [])),
            quiet=bool(data.get("quiet", False)),
            keywords=list(data.get("keywords", [])),
        )

    async def compose(
        self, conditions: list[Condition], rows: list[DiscoverRow], total: int
    ) -> ComposeResult:
        rows_json = json.dumps(
            [
                {
                    "contentId": r.content_id,
                    "title": r.title,
                    "category": r.category,
                    "region": r.region_label,
                    "overviewHead": r.overview_head,
                    "quiet": r.quiet,
                }
                for r in rows
            ],
            ensure_ascii=False,
        )
        cond_desc = ", ".join(f"{c.kind}:{c.label}" for c in conditions) or "없음"
        data = await self._tool_call(
            f"누적 조건: {cond_desc}\n총 후보 수: {total}\n카드 데이터: {rows_json}\n"
            "bot_text는 후보 수를 언급하는 따뜻한 안내 1~2문장. whys는 카드마다 위 데이터 "
            "필드에만 근거한 선정 이유 1줄(quiet=true면 한산함 언급 가능).",
            _COMPOSE_TOOL,
        )
        if data is None:
            return await self._fallback.compose(conditions, rows, total)
        whys = {w["contentId"]: w["why"] for w in data.get("whys", []) if "contentId" in w}
        for r in rows:
            whys.setdefault(r.content_id, r.category or "조건과 결이 맞는 곳")
        return ComposeResult(
            bot_text=str(data.get("bot_text", "")) or f"{total}곳이 남았어요.",
            whys=whys,
        )


def build_chat_llm() -> ChatLLM:
    if settings.ANTHROPIC_API_KEY:
        return AnthropicChatLLM()
    return HeuristicChatLLM()
