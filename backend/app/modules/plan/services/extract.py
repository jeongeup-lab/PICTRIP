from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.core.logging import get_logger
from app.modules.plan import llm
from app.modules.plan.errors import PlanLlmUnavailable, PlanNoPlacesFound
from app.modules.plan.schemas import ExtractedPlace
from app.modules.plan.services.ingest import IngestInput

logger = get_logger(__name__)

MAX_TRIP_DAYS = 7

_SYSTEM_PROMPT = """\
너는 여행 콘텐츠에서 장소를 추출하는 도우미다.
입력은 여행 콘텐츠(영상 자막, 글, 또는 스크린샷)다. 아래 규칙대로 장소를 추출해 JSON으로 반환한다.

규칙:
- 콘텐츠에 이름이 실제로 언급되거나 화면에 보이는 장소만 추출한다. 추측으로 장소를 만들어내지 않는다.
- 콘텐츠 전체를 처음부터 끝까지 훑어, 언급된 장소를 하나도 빠뜨리지 않고 모두 추출한다. 목록이 길어도 줄이지 않는다.
- 대한민국 안의 장소만 포함한다. 해외 장소는 제외한다.
- name은 콘텐츠에 나온 표기 그대로 적는다.
- nameKo는 한국어 정식 명칭으로 정규화한다(예: "Gamcheon Village" → "감천문화마을"). 이미 한국어면 그대로 둔다.
- placeType: attraction(관광지·명소), restaurant(식당·맛집), cafe(카페·디저트·빵집), hotel(숙소), region(도시·지역 자체) 중 하나.
- regionHint: 그 장소가 속한 지역명(예: "여수", "부산 해운대구"). 콘텐츠에서 알 수 없으면 넣지 않는다.
- orderHint: 콘텐츠에 등장한 순서(1부터 정수).
- tip: 콘텐츠가 그 장소에 대해 말한 팁이나 감상 한 줄. 없으면 넣지 않는다.
- tripDays: 콘텐츠가 며칠 여행인지 명시하면 그 일수(예: "1박2일" → 2, "2박3일" → 3). 명시가 없으면 넣지 않는다.
- 자동 생성 자막은 지명에 오탈자가 있을 수 있다. 문맥상 명백한 경우에만 바로잡아 nameKo에 반영한다.
- 같은 장소가 여러 번 나오면 한 번만 넣는다.
- 장소가 하나도 없으면 places를 빈 배열로 반환한다.
"""

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "places": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "nameKo": {"type": "STRING", "nullable": True},
                    "placeType": {
                        "type": "STRING",
                        "enum": ["attraction", "restaurant", "cafe", "hotel", "region"],
                    },
                    "regionHint": {"type": "STRING", "nullable": True},
                    "tip": {"type": "STRING", "nullable": True},
                    "orderHint": {"type": "INTEGER", "nullable": True},
                },
                "required": ["name", "placeType"],
            },
        },
        "tripDays": {"type": "INTEGER", "nullable": True},
    },
    "required": ["places"],
}


@dataclass(slots=True)
class Extraction:
    places: list[ExtractedPlace] = field(default_factory=list)
    trip_days: int | None = None


async def extract_places(source: IngestInput) -> Extraction:
    data = await llm.get_client().generate_json(
        system=_SYSTEM_PROMPT,
        user_text=_build_user_text(source),
        image_bytes=source.image_bytes,
        image_mime=source.mime,
        response_schema=_RESPONSE_SCHEMA,
    )
    if not isinstance(data, dict) or not isinstance(data.get("places"), list):
        raise PlanLlmUnavailable()
    places = _validate_places(data["places"])
    if not places:
        raise PlanNoPlacesFound()
    trip_days = data.get("tripDays")
    if not isinstance(trip_days, int) or not 1 <= trip_days <= MAX_TRIP_DAYS:
        trip_days = None
    logger.info(
        "plan.extract.done",
        source_kind=source.kind,
        place_count=len(places),
        trip_days=trip_days,
    )
    return Extraction(places=places, trip_days=trip_days)


def _validate_places(raw_places: list[Any]) -> list[ExtractedPlace]:
    places: list[ExtractedPlace] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_places):
        try:
            place = ExtractedPlace.model_validate(raw)
        except ValidationError:
            continue
        key = (place.nameKo or place.name).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        if place.orderHint is None:
            place.orderHint = index + 1
        places.append(place)
    return places


def _build_user_text(source: IngestInput) -> str:
    if source.kind == "image":
        return "이 스크린샷에서 규칙대로 장소를 추출해라."
    lines = []
    if source.source_title:
        lines.append(f"[제목] {source.source_title}")
    if source.source_description:
        lines.append(f"[설명란] {source.source_description}")
    lines.append(f"[본문] {source.raw_text or ''}")
    return "\n".join(lines)
