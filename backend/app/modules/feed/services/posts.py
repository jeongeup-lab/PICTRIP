from __future__ import annotations

import base64
import binascii
import secrets
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.feed import repositories
from app.modules.feed.repositories import OverseasPostRow
from app.modules.feed.schemas import MatchCard, OverseasPost
from app.modules.feed.services import matching
from app.web.errors import ValidationFailed


@dataclass(frozen=True)
class PostsPageRow:
    seed: str
    items: list[OverseasPostRow]
    next_cursor: str | None
    has_more: bool
    matches: dict[int, list[matching.MatchRow]]


def to_match_card(row: matching.MatchRow) -> MatchCard:
    return MatchCard(
        contentId=row.content_id,
        title=row.title,
        regionLabel=row.region_label,
        imageUrl=matching.display_image_url(row),
        overviewFirst=row.overview_first,
    )


def to_post(row: OverseasPostRow, matches: list[matching.MatchRow]) -> OverseasPost:
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
        matches=[to_match_card(match) for match in matches],
    )


def _encode_cursor(row: OverseasPostRow) -> str:
    return base64.urlsafe_b64encode(f"{row.shuffle_key!r}:{row.id}".encode()).decode()


def _decode_cursor(cursor: str | None) -> tuple[float | None, int | None]:
    if not cursor:
        return None, None
    try:
        key, sep, oid = base64.urlsafe_b64decode(cursor.encode()).decode().partition(":")
        if not sep:
            raise ValueError
        return float(key), int(oid)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise ValidationFailed("invalid cursor") from exc


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
    items = _spread_countries(page)
    return PostsPageRow(
        seed=seed,
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
        matches=await matching.load_matches_by_post(session, [row.id for row in items]),
    )
