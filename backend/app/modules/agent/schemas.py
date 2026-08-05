from __future__ import annotations

from typing import Annotated, Literal, get_args

from pydantic import BaseModel, Field, StringConstraints, computed_field

PlaceType = Literal["attraction", "restaurant", "cafe", "hotel", "region"]
ResolveStatus = Literal["matched", "ambiguous", "naver_only", "unmatched"]
CrowdPreference = Literal["quiet", "any", "popular"]
Mood = Literal["sea", "mountain", "lake", "island", "hanok", "night", "street"]
DropAxis = Literal["crowd", "indoor", "near", "region", "category"]
AnchorAction = Literal["food", "cafe", "nearby", "crowd"]

MAX_KEYWORDS = 20
MAX_REGION_HINTS = 20
MAX_NAMED_PLACES = 10
MAX_MOOD_HINTS = len(get_args(Mood))
MAX_TEXT_CHARS = 80
MAX_HINT_TOKENS = 4
MAX_CONTEXT_SPOTS = 8

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
    categoryKeywords: list[IntentText] = Field(default_factory=list, max_length=MAX_KEYWORDS)
    regionHints: list[IntentText] = Field(default_factory=list, max_length=MAX_REGION_HINTS)
    namedPlaces: list[ExtractedPlace] = Field(default_factory=list, max_length=MAX_NAMED_PLACES)
    crowdPreference: CrowdPreference = "any"
    moodHints: list[Mood] = Field(default_factory=list, max_length=MAX_MOOD_HINTS)
    festivalOnly: bool = False
    indoorOnly: bool = False
    nearMe: bool = False
    outOfScope: bool = False


class RefinePatch(BaseModel):
    crowdPreference: CrowdPreference | None = None
    indoorOnly: bool | None = None
    nearMe: bool | None = None
    drop: DropAxis | None = None


class Suggestion(BaseModel):
    label: str
    patch: RefinePatch


PRE_OTA_REGION_PREFIXES: dict[str, tuple[str, ...]] = {
    "all": (),
    "capital": ("서울", "경기", "인천"),
    "gangwon": ("강원",),
    "chungcheong": ("충청", "충북", "충남", "대전", "세종"),
    "jeolla": ("전라", "전북", "전남", "광주"),
    "gyeongsang": ("경상", "경북", "경남", "대구", "울산", "부산"),
    "jeju": ("제주",),
}


class AskAnchor(BaseModel):
    contentId: Annotated[str, StringConstraints(min_length=1, max_length=32)] | None = None
    action: AnchorAction


class AskContextSpot(BaseModel):
    contentId: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    title: IntentText


class AskContext(BaseModel):
    intent: QueryIntent | None = None
    spots: list[AskContextSpot] = Field(default_factory=list, max_length=MAX_CONTEXT_SPOTS)


class AskRequest(BaseModel):
    question: str | None = None
    lat: float | None = Field(None, ge=-90.0, le=90.0)
    lng: float | None = Field(None, ge=-180.0, le=180.0)
    intent: QueryIntent | None = None
    patch: RefinePatch | None = None
    anchor: AskAnchor | None = None
    context: AskContext | None = None
    region: str | None = None

    @property
    def pre_ota_region_prefixes(self) -> list[str]:
        return list(PRE_OTA_REGION_PREFIXES.get(self.region or "all", ()))


class AskStep(BaseModel):
    tool: ToolName
    label: str
    badge: str


class AnswerSegment(BaseModel):
    text: str
    emphasis: bool = False


class AgentSpotCard(BaseModel):
    contentId: str
    title: str
    regionLabel: str
    imageUrl: str | None = None
    tag: str | None = None
    lat: float | None = None
    lng: float | None = None
    hasCrowd: bool = False
    blurb: str | None = None


class AskResponse(BaseModel):
    steps: list[AskStep]
    answer: list[AnswerSegment]
    spots: list[AgentSpotCard]
    totalCount: int
    intent: QueryIntent
    refinements: list[Suggestion]
    tagBasis: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def suggestions(self) -> list[str]:
        return [
            refinement.label for refinement in self.refinements if refinement.patch.drop is None
        ]
