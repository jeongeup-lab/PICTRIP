from __future__ import annotations

import asyncio
import re

from app.core.db import AsyncSession
from app.core.logging import get_logger
from app.ml.embedding import embedder
from app.modules.agent import repositories
from app.modules.agent.repositories import CandidateRow
from app.modules.agent.services import photo as photo_service

logger = get_logger(__name__)

SCENE_PROMPTS: dict[str, str] = {
    "단풍": "a photo of autumn foliage with red and yellow maple leaves on trees",
    "설경": "a photo of a snow covered winter landscape with snowy trees",
    "벚꽃": "a photo of cherry blossom trees in full bloom with pink flowers",
    "억새": "a photo of a field of silver grass pampas swaying in the wind",
    "갈대": "a photo of a field of silver grass pampas swaying in the wind",
    "유채꽃": "a photo of a bright yellow canola flower field in bloom",
    "일출": "a photo of a sunrise over the horizon with orange sky",
    "일몰": "a photo of a sunset over the horizon with orange and purple sky",
    "노을": "a photo of a sunset over the horizon with orange and purple sky",
    "안개": "a photo of a misty foggy landscape with low clouds",
    "별": "a photo of a starry night sky with the milky way over a landscape",
    "은하수": "a photo of a starry night sky with the milky way over a landscape",
}

ALIASES: dict[str, str] = {
    "단풍철": "단풍",
    "낙엽": "단풍",
    "눈꽃": "설경",
    "설화": "설경",
    "벚꽃길": "벚꽃",
    "벚나무": "벚꽃",
    "핑크뮬리": "억새",
    "코스모스": "유채꽃",
    "해돋이": "일출",
    "해넘이": "일몰",
    "석양": "일몰",
    "운해": "안개",
    "밤하늘": "별",
}

_WORD = re.compile(r"[가-힣]+")
_vectors: dict[str, list[float]] = {}


def detect(question: str, keywords: list[str]) -> str | None:
    """계절·현상처럼 분류 코드로 못 담는 장면을 집는다.

    moodHints 는 7코드 고정이라 단풍·설경이 들어갈 자리가 없다. 이름으로도 안 걸린다 —
    '우화정' 은 내장산 단풍 명소지만 제목에 단풍이 없다. 사진이 유일한 단서다.
    """
    for token in _WORD.findall(f"{question} {' '.join(keywords)}"):
        for term in (token, ALIASES.get(token, "")):
            if term in SCENE_PROMPTS:
                return term
        for known in SCENE_PROMPTS:
            if known in token:
                return known
        for alias, term in ALIASES.items():
            if alias in token:
                return term
    return None


async def _vector(term: str) -> list[float]:
    cached = _vectors.get(term)
    if cached is not None:
        return cached
    vector = (await asyncio.to_thread(embedder.embed_texts, [SCENE_PROMPTS[term]]))[0]
    _vectors[term] = vector
    return vector


async def search(
    session: AsyncSession, term: str, *, region_prefixes: list[str]
) -> list[CandidateRow]:
    """장면 문구를 임베딩해 사진이 닮은 곳을 찾는다."""
    matched = await photo_service.match_vector(
        session, await _vector(term), region_prefixes=region_prefixes
    )
    briefs = await repositories.load_candidates_by_ids(session, [row.content_id for row in matched])
    found = [briefs[row.content_id] for row in matched if row.content_id in briefs]
    logger.info("agent.scene.done", term=term, matches=len(found))
    return found
