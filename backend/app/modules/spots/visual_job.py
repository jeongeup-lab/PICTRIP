from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from sqlalchemy import text

from app.core.db import async_session_factory
from app.core.logging import get_logger

logger = get_logger(__name__)

TYPE_PROMPTS: dict[str, list[str]] = {
    "interior": [
        "a photo of the inside of a coffee shop with tables, chairs and a counter",
        "a photo of a cafe interior room with furniture and lighting",
    ],
    "exterior": [
        "a photo of a building facade with a signboard taken from the street",
        "a photo of the outside of a cafe building with its entrance",
    ],
    "food": [
        "a close-up photo of a coffee cup or latte art on a table",
        "a close-up photo of bread, cake or dessert",
    ],
    "view": [
        "a wide landscape photo of the sea, mountains or fields",
        "a scenic nature panorama with the horizon",
    ],
}

AESTHETIC_PROMPTS: dict[str, tuple[list[str], list[str]]] = {
    "interior": (
        [
            "a stunning aesthetic cafe interior with warm mood lighting, stylish furniture and plants",
            "an instagrammable minimalist cafe interior with beautiful natural light",
        ],
        [
            "a plain cheap cafe interior with fluorescent lights and plastic chairs",
            "a cluttered outdated shop interior",
        ],
    ),
    "exterior": (
        [
            "a beautiful unique cafe building with charming architecture, hanok or seaside design",
            "a photogenic cafe facade with lovely landscaping",
        ],
        [
            "a parking lot full of cars in front of a commercial building",
            "a dull roadside commercial building with cluttered signboards",
        ],
    ),
    "food": (
        ["an artfully plated dessert and latte with beautiful food styling in soft light"],
        ["unappetizing food in harsh flash light on a messy table"],
    ),
    "view": (
        ["a breathtaking scenic ocean or forest view from a cafe terrace at golden hour"],
        ["a dull view of asphalt road and power lines"],
    ),
}

_TARGETS_SQL = """
SELECT e.content_id, e.embedding::text AS embedding
FROM spot_embeddings e
JOIN spots s ON s.content_id = e.content_id
WHERE s.show_flag = 1
  AND s.first_image_url IS NOT NULL
  AND s.first_image_url <> ''
ORDER BY e.content_id
LIMIT :lim OFFSET :off
"""

_UPSERT_SQL = """
INSERT INTO spot_visual (content_id, photo_type, aesthetic_score, computed_at)
VALUES (:content_id, :photo_type, :aesthetic_score, now())
ON CONFLICT (content_id) DO UPDATE SET
    photo_type = EXCLUDED.photo_type,
    aesthetic_score = EXCLUDED.aesthetic_score,
    computed_at = now()
"""

_BATCH = 2000


@dataclass(frozen=True)
class VisualAnchors:
    type_keys: list[str]
    type_vectors: list[list[float]]
    aesthetic: dict[str, tuple[list[float], list[float]]]


@dataclass
class VisualResult:
    scored: int = 0
    by_type: dict[str, int] = field(default_factory=dict)


def _mean_unit(vectors: list[list[float]]) -> list[float]:
    dim = len(vectors[0])
    mean = [sum(v[i] for v in vectors) / len(vectors) for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in mean)) or 1.0
    return [x / norm for x in mean]


def build_anchors(embed_texts) -> VisualAnchors:  # type: ignore[no-untyped-def]
    type_keys = list(TYPE_PROMPTS)
    type_vectors = [_mean_unit(embed_texts(TYPE_PROMPTS[k])) for k in type_keys]
    aesthetic = {
        k: (_mean_unit(embed_texts(pos)), _mean_unit(embed_texts(neg)))
        for k, (pos, neg) in AESTHETIC_PROMPTS.items()
    }
    return VisualAnchors(type_keys=type_keys, type_vectors=type_vectors, aesthetic=aesthetic)


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def score_embedding(vector: list[float], anchors: VisualAnchors) -> tuple[str, float]:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    unit = [x / norm for x in vector]
    sims = [_dot(unit, t) for t in anchors.type_vectors]
    photo_type = anchors.type_keys[sims.index(max(sims))]
    pos, neg = anchors.aesthetic[photo_type]
    return photo_type, _dot(unit, pos) - _dot(unit, neg)


async def run_visual_job(*, limit: int | None = None) -> VisualResult:
    from app.ml.embedding import embedder

    anchors = build_anchors(embedder.embed_texts)
    result = VisualResult()
    offset = 0
    while True:
        batch = min(_BATCH, limit - result.scored) if limit is not None else _BATCH
        if batch <= 0:
            break
        async with async_session_factory() as session:
            rows = (await session.execute(text(_TARGETS_SQL), {"lim": batch, "off": offset})).all()
            if not rows:
                break
            for row in rows:
                vector = json.loads(row.embedding)
                photo_type, score = score_embedding(vector, anchors)
                await session.execute(
                    text(_UPSERT_SQL),
                    {
                        "content_id": row.content_id,
                        "photo_type": photo_type,
                        "aesthetic_score": score,
                    },
                )
                result.scored += 1
                result.by_type[photo_type] = result.by_type.get(photo_type, 0) + 1
            await session.commit()
        offset += len(rows)
        logger.info("visual.batch_done", scored=result.scored)
    return result
