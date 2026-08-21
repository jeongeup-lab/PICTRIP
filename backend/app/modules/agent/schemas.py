from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, get_args
from uuid import uuid4

from pydantic import BaseModel, Field, StringConstraints, field_validator

PlaceType = Literal["attraction", "restaurant", "cafe", "hotel", "region"]
ResolveStatus = Literal["matched", "ambiguous", "naver_only", "unmatched"]
CrowdPreference = Literal["quiet", "any", "popular"]
Mood = Literal["sea", "mountain", "lake", "island", "hanok", "night", "street"]
DropAxis = Literal["crowd", "indoor", "near", "region", "category"]
AnchorAction = Literal["food", "cafe", "nearby", "crowd", "related"]
TaskKind = Literal["search", "detail", "smalltalk", "unsupported"]
DetailField = Literal["hours", "closed", "parking", "contact", "fee", "overview"]

MAX_KEYWORDS = 20
MAX_REGION_HINTS = 20
MAX_NAMED_PLACES = 10
MAX_MOOD_HINTS = len(get_args(Mood))
MAX_TEXT_CHARS = 80
MAX_HINT_TOKENS = 4
MAX_CONTEXT_SPOTS = 8
MAX_TITLE_CHARS = 255
MAX_DETAIL_FIELDS = 6
MAX_MESSAGE_CHARS = 500
MAX_HISTORY_ITEMS = 8
MAX_HISTORY_SPOT_IDS = 8
MAX_CARD_CHIPS = 3
MAX_SUB_QUESTIONS = 3

IntentText = Annotated[str, StringConstraints(max_length=MAX_TEXT_CHARS)]

ToolName = Literal[
    "intent",
    "photo_match",
    "resolve_place",
    "category_search",
    "mood_search",
    "festival",
    "title_search",
    "concentration",
    "nearby",
    "related",
    "spot_detail",
    "compare_regions",
    "region_profile",
    "similar_region",
]


class ExtractedPlace(BaseModel):
    name: IntentText
    nameKo: IntentText | None = None
    placeType: PlaceType = "attraction"
    regionHint: IntentText | None = None
    tip: IntentText | None = None
    orderHint: int | None = None


class ResolvedSpot(BaseModel):
    source: Literal["kto", "naver"] = "kto"
    contentId: str | None = None
    title: str
    category: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    imageUrl: str | None = None


class ResolvedPlace(BaseModel):
    extracted: ExtractedPlace
    spot: ResolvedSpot | None = None
    confidence: float = 0.0
    status: ResolveStatus = "unmatched"


class QueryIntent(BaseModel):
    task: TaskKind = "search"
    targetPlace: Annotated[str, StringConstraints(max_length=MAX_TITLE_CHARS)] | None = None
    detailFields: list[DetailField] = Field(default_factory=list, max_length=MAX_DETAIL_FIELDS)
    categoryKeywords: list[IntentText] = Field(default_factory=list, max_length=MAX_KEYWORDS)
    regionHints: list[IntentText] = Field(default_factory=list, max_length=MAX_REGION_HINTS)
    namedPlaces: list[ExtractedPlace] = Field(default_factory=list, max_length=MAX_NAMED_PLACES)
    crowdPreference: CrowdPreference = "any"
    moodHints: list[Mood] = Field(default_factory=list, max_length=MAX_MOOD_HINTS)
    festivalOnly: bool = False
    originPlace: Annotated[str, StringConstraints(max_length=MAX_TITLE_CHARS)] | None = None
    aroundOrigin: bool = False
    indoorOnly: bool = False
    nearMe: bool = False
    outOfScope: bool = False
    subQuestions: list[IntentText] = Field(default_factory=list, max_length=MAX_SUB_QUESTIONS)


class RefinePatch(BaseModel):
    crowdPreference: CrowdPreference | None = None
    indoorOnly: bool | None = None
    nearMe: bool | None = None
    drop: DropAxis | None = None


class Suggestion(BaseModel):
    label: str
    patch: RefinePatch


class AskAnchor(BaseModel):
    contentId: Annotated[str, StringConstraints(min_length=1, max_length=32)] | None = None
    action: AnchorAction


class AskContextSpot(BaseModel):
    contentId: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    title: Annotated[str, StringConstraints(min_length=1, max_length=MAX_TITLE_CHARS)]


class AskContext(BaseModel):
    intent: QueryIntent | None = None
    focusContentId: Annotated[str, StringConstraints(min_length=1, max_length=32)] | None = None
    spots: list[AskContextSpot] = Field(default_factory=list, max_length=MAX_CONTEXT_SPOTS)


class AskRequest(BaseModel):
    question: Annotated[str, StringConstraints(max_length=MAX_MESSAGE_CHARS)] | None = None
    lat: float | None = Field(None, ge=-90.0, le=90.0)
    lng: float | None = Field(None, ge=-180.0, le=180.0)
    intent: QueryIntent | None = None
    patch: RefinePatch | None = None
    anchor: AskAnchor | None = None
    context: AskContext | None = None


class ChatHistoryItem(BaseModel):
    """대화 이력은 참고 자료다 — 넘치면 잘라 쓰고, 턴 전체를 거절하지 않는다."""

    role: Literal["user", "assistant"]
    text: Annotated[str, StringConstraints(max_length=MAX_MESSAGE_CHARS)]
    spotIds: list[Annotated[str, StringConstraints(min_length=1, max_length=32)]] = Field(
        default_factory=list
    )

    @field_validator("text", mode="before")
    @classmethod
    def _clip_text(cls, value: object) -> object:
        return value[:MAX_MESSAGE_CHARS] if isinstance(value, str) else value

    @field_validator("spotIds", mode="before")
    @classmethod
    def _clip_spot_ids(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        kept = [item for item in value if isinstance(item, str) and 0 < len(item) <= 32]
        return kept[:MAX_HISTORY_SPOT_IDS]


class ChatRequest(BaseModel):
    clientRequestId: Annotated[str, StringConstraints(min_length=1, max_length=128)] = Field(
        default_factory=lambda: uuid4().hex
    )
    message: Annotated[str, StringConstraints(max_length=MAX_MESSAGE_CHARS)] | None = None
    lat: float | None = Field(None, ge=-90.0, le=90.0)
    lng: float | None = Field(None, ge=-180.0, le=180.0)
    clientTime: datetime | None = None
    context: AskContext | None = None
    intent: QueryIntent | None = None
    patch: RefinePatch | None = None
    history: list[ChatHistoryItem] = Field(default_factory=list)

    @field_validator("history", mode="before")
    @classmethod
    def _clip_history(cls, value: object) -> object:
        return value[-MAX_HISTORY_ITEMS:] if isinstance(value, list) else value


SourceKind = Literal["naver_blog", "kto", "kakao"]


class SourceItem(BaseModel):
    kind: SourceKind
    title: str
    url: str | None = None
    date: str | None = None


class AskStep(BaseModel):
    tool: ToolName
    label: str
    badge: str


class AnswerSegment(BaseModel):
    text: str
    emphasis: bool = False


CardSource = Literal["kto", "kakao"]


class AgentSpotCard(BaseModel):
    contentId: str
    title: str
    regionLabel: str
    imageUrl: str | None = None
    fallbackImageUrl: str | None = None
    tag: str | None = None
    lat: float | None = None
    lng: float | None = None
    categoryGroup: str | None = None
    chips: list[str] = Field(default_factory=list, max_length=MAX_CARD_CHIPS)
    hasCrowd: bool = False
    source: CardSource = "kto"
    externalUrl: str | None = None
    phone: str | None = None
    distanceM: int | None = None
    saveable: bool = True


class AskResponse(BaseModel):
    steps: list[AskStep]
    answer: list[AnswerSegment]
    spots: list[AgentSpotCard]
    totalCount: int
    intent: QueryIntent
    refinements: list[Suggestion]
    tagBasis: str | None = None
    unmet: list[str] = Field(default_factory=list)


class ChatStepEvent(BaseModel):
    index: int
    label: str
    badge: str | None = None
    status: Literal["run", "done"]


class ChatDeltaEvent(BaseModel):
    text: str


class ChatCardsEvent(BaseModel):
    spots: list[AgentSpotCard]
    tagBasis: str | None = None
    applied: list[str] = Field(default_factory=list)
    refinements: list[Suggestion] = Field(default_factory=list)


class ChatSourcesEvent(BaseModel):
    items: list[SourceItem]


class ChatDoneEvent(BaseModel):
    answerText: str
    spots: list[AgentSpotCard]
    sources: list[SourceItem]
    intent: QueryIntent
    totalCount: int
    applied: list[str] = Field(default_factory=list)
    refinements: list[Suggestion] = Field(default_factory=list)
    traceId: str | None = None


class ChatErrorEvent(BaseModel):
    code: str
    message: str
