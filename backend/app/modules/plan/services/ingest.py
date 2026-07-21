from __future__ import annotations

from dataclasses import dataclass

from app.modules.plan import youtube
from app.modules.plan.errors import PlanSourceInvalid
from app.modules.plan.schemas import SourceKind
from app.web.errors import ImageInvalid

MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/heic"}
MAX_TEXT_CHARS = 20_000


@dataclass(slots=True)
class IngestInput:
    kind: SourceKind
    raw_text: str | None = None
    image_bytes: bytes | None = None
    mime: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    source_description: str | None = None
    lang_hint: str | None = None


async def normalize(
    *,
    text: str | None,
    url: str | None,
    image_bytes: bytes | None,
    image_mime: str | None,
) -> IngestInput:
    if image_bytes:
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise ImageInvalid()
        if image_mime not in ALLOWED_IMAGE_MIMES:
            raise ImageInvalid()
        return IngestInput(kind="image", image_bytes=image_bytes, mime=image_mime)
    if url and url.strip():
        content = await youtube.fetch_content(url.strip())
        return IngestInput(
            kind="youtube",
            raw_text=content.text,
            source_url=url.strip(),
            source_title=content.title,
            source_description=content.description,
            lang_hint=content.lang,
        )
    if text and text.strip():
        return IngestInput(kind="text", raw_text=text.strip()[:MAX_TEXT_CHARS])
    raise PlanSourceInvalid()
