from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx
from youtube_transcript_api import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    Transcript,
    TranscriptList,
    YouTubeTranscriptApi,
)

from app.config import settings
from app.core.logging import get_logger
from app.modules.plan.errors import PlanSourceInvalid, PlanTranscriptUnavailable

logger = get_logger(__name__)

_WATCH_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
_SHORT_HOSTS = {"youtu.be", "www.youtu.be"}
_PATH_PREFIXES = {"shorts", "live", "embed"}
_OEMBED_URL = "https://www.youtube.com/oembed"
_PREFERRED_LANGS = ["ko", "en"]


MAX_TRANSCRIPT_CHARS = 30_000
MAX_DESCRIPTION_CHARS = 5_000

_DATA_API_URL = "https://www.googleapis.com/youtube/v3/videos"


@dataclass(slots=True)
class YoutubeContent:
    video_id: str
    title: str | None
    description: str | None
    text: str
    lang: str


def extract_video_id(url: str) -> str | None:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower()
    if host in _SHORT_HOSTS:
        return parsed.path.strip("/").split("/")[0] or None
    if host in _WATCH_HOSTS:
        if parsed.path == "/watch":
            values = parse_qs(parsed.query).get("v") or []
            return values[0] if values else None
        parts = parsed.path.strip("/").split("/")
        if len(parts) == 2 and parts[0] in _PATH_PREFIXES:
            return parts[1] or None
    return None


def is_youtube_url(url: str) -> bool:
    return extract_video_id(url) is not None


async def fetch_content(url: str) -> YoutubeContent:
    video_id = extract_video_id(url)
    if not video_id:
        raise PlanSourceInvalid("유튜브 링크 형식이 아닙니다.")
    (title, description), (text, lang) = await asyncio.gather(
        _fetch_meta(video_id),
        asyncio.to_thread(_fetch_transcript, video_id),
    )
    logger.info(
        "plan.youtube.fetched",
        video_id=video_id,
        lang=lang,
        transcript_chars=len(text),
        has_title=title is not None,
        has_description=description is not None,
    )
    return YoutubeContent(
        video_id=video_id,
        title=title,
        description=description,
        text=text[:MAX_TRANSCRIPT_CHARS],
        lang=lang,
    )


def _fetch_transcript(video_id: str) -> tuple[str, str]:
    try:
        transcripts = YouTubeTranscriptApi().list(video_id)
    except CouldNotRetrieveTranscript as exc:
        raise PlanTranscriptUnavailable() from exc
    for transcript in _candidates(transcripts):
        try:
            fetched = transcript.fetch()
        except CouldNotRetrieveTranscript:
            continue
        text = " ".join(
            snippet.text.strip()
            for snippet in fetched
            if snippet.text.strip() and not snippet.text.strip().startswith("[")
        )
        if text:
            return text, fetched.language_code
    raise PlanTranscriptUnavailable()


def _candidates(transcripts: TranscriptList) -> list[Transcript]:
    found = []
    for lang in _PREFERRED_LANGS:
        for finder in (
            transcripts.find_manually_created_transcript,
            transcripts.find_generated_transcript,
        ):
            try:
                found.append(finder([lang]))
            except NoTranscriptFound:
                continue
    return found


async def _fetch_meta(video_id: str) -> tuple[str | None, str | None]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        if settings.YOUTUBE_API_KEY:
            meta = await _fetch_meta_data_api(client, video_id)
            if meta is not None:
                return meta
        return await _fetch_title_oembed(client, video_id), None


async def _fetch_meta_data_api(
    client: httpx.AsyncClient, video_id: str
) -> tuple[str | None, str | None] | None:
    try:
        resp = await client.get(
            _DATA_API_URL,
            params={"part": "snippet", "id": video_id, "key": settings.YOUTUBE_API_KEY},
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return None
        snippet = items[0].get("snippet", {})
        title = snippet.get("title")
        description = snippet.get("description")
        return (
            title if isinstance(title, str) else None,
            description[:MAX_DESCRIPTION_CHARS]
            if isinstance(description, str) and description.strip()
            else None,
        )
    except (httpx.HTTPError, ValueError):
        return None


async def _fetch_title_oembed(client: httpx.AsyncClient, video_id: str) -> str | None:
    try:
        resp = await client.get(
            _OEMBED_URL,
            params={
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "format": "json",
            },
        )
        resp.raise_for_status()
        title = resp.json().get("title")
        return title if isinstance(title, str) else None
    except (httpx.HTTPError, ValueError):
        return None
