from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartParser

from app.core.db import DbSession
from app.kto.client import KtoDep
from app.modules.agent.schemas import AskRequest
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services.photo import MAX_IMAGE_BYTES
from app.web.envelope import ok
from app.web.errors import ImageInvalid, ValidationFailed
from app.web.ratelimit import rate_limit

FORM_OVERHEAD_BYTES = 64 * 1024
MAX_BODY_BYTES = MAX_IMAGE_BYTES + FORM_OVERHEAD_BYTES

MultiPartParser.spool_max_size = MAX_BODY_BYTES

router = APIRouter(tags=["AGT · travel agent"])


@router.post(
    "/agent/ask",
    summary="여행 탭 질의 — 자유문·사진 → 단계 + 답변 + 스팟",
    dependencies=[Depends(rate_limit(bucket="agent_ask", limit=20, window_seconds=60))],
)
async def agent_ask(request: Request, session: DbSession, kto: KtoDep) -> dict[str, Any]:
    payload, image_bytes, image_mime = await _read_payload(request)
    result = await ask_service.ask(
        session,
        kto,
        question=payload.question,
        lat=payload.lat,
        lng=payload.lng,
        image_bytes=image_bytes,
        image_mime=image_mime,
        intent=payload.intent,
        patch=payload.patch,
    )
    return ok(result)


async def _buffer_capped(request: Request) -> None:
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_BODY_BYTES:
            raise ImageInvalid()
        chunks.append(chunk)
    request._body = b"".join(chunks)


async def _read_payload(request: Request) -> tuple[AskRequest, bytes | None, str | None]:
    await _buffer_capped(request)
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/"):
        form = await request.form()
        upload = form.get("photo")
        image_bytes = None
        image_mime = None
        if isinstance(upload, UploadFile):
            image_bytes = await _read_capped(upload)
            image_mime = upload.content_type
        fields: dict[str, Any] = {
            key: value
            for key, value in form.multi_items()
            if key != "photo" and isinstance(value, str) and value != ""
        }
        for key in ("intent", "patch"):
            raw = fields.get(key)
            if isinstance(raw, str):
                try:
                    fields[key] = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValidationFailed(f"invalid {key} json") from exc
        return _parse(fields), image_bytes, image_mime
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationFailed("invalid json body") from exc
    if not isinstance(body, dict):
        raise ValidationFailed("body must be an object")
    return _parse(body), None, None


def _parse(raw: dict[str, Any]) -> AskRequest:
    try:
        return AskRequest.model_validate(raw)
    except ValidationError as exc:
        raise ValidationFailed("invalid ask payload") from exc


async def _read_capped(upload: UploadFile) -> bytes:
    payload = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(payload) > MAX_IMAGE_BYTES:
        raise ImageInvalid()
    return payload
