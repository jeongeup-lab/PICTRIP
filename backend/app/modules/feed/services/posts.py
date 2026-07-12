from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.feed import repositories
from app.modules.feed.repositories import OverseasPostRow
from app.modules.feed.schemas import OverseasPost


@dataclass(frozen=True)
class PostsPageRow:
    seed: str
    items: list[OverseasPostRow]
    next_cursor: str | None
    has_more: bool


def to_post(row: OverseasPostRow) -> OverseasPost:
    return OverseasPost(
        id=row.id,
        nameKo=row.name_ko,
        countryCode=row.country_code,
        countryNameKo=row.country_name_ko,
        descriptionKo=row.description_ko,
        imageUrl=row.image_url,
        imageAuthor=row.image_author,
        imageLicense=row.image_license,
        imageLicenseUrl=row.image_license_url,
        imageSourceUrl=row.image_source_url,
    )


def _encode_cursor(row: OverseasPostRow) -> str:
    return base64.urlsafe_b64encode(f"{row.shuffle_key!r}:{row.id}".encode()).decode()


def _decode_cursor(cursor: str | None) -> tuple[float | None, int | None]:
    if not cursor:
        return None, None
    key, _, oid = base64.urlsafe_b64decode(cursor.encode()).decode().partition(":")
    return float(key), int(oid)


def _spread_countries(items: list[OverseasPostRow]) -> list[OverseasPostRow]:
    out = list(items)
    for i in range(1, len(out)):
        if out[i].country_code != out[i - 1].country_code:
            continue
        for j in range(i + 1, len(out)):
            if out[j].country_code != out[i - 1].country_code:
                out[i], out[j] = out[j], out[i]
                break
    return out


async def list_posts(
    session: AsyncSession, *, seed: str | None, cursor: str | None, limit: int
) -> PostsPageRow:
    seed = seed or secrets.token_hex(8)
    cursor_key, cursor_id = _decode_cursor(cursor)
    rows = await repositories.fetch_posts_page(
        session, seed=seed, cursor_key=cursor_key, cursor_id=cursor_id, limit=limit + 1
    )
    has_more = len(rows) > limit
    page = rows[:limit]
    tail = page[-1] if page else None
    next_cursor = _encode_cursor(tail) if tail and has_more else None
    return PostsPageRow(
        seed=seed,
        items=_spread_countries(page),
        next_cursor=next_cursor,
        has_more=has_more,
    )
