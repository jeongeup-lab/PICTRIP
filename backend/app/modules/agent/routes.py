from __future__ import annotations

import json
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartParser

from app.core.db import DbSession
from app.core.redis import RedisDep
from app.kto.client import KtoDep
from app.modules.agent.schemas import AskRequest, ChatRequest
from app.modules.agent.services import ask as ask_service
from app.modules.agent.services import chat as chat_service
from app.modules.agent.services import moods as moods_service
from app.modules.agent.services.photo import MAX_IMAGE_BYTES
from app.web.envelope import ok
from app.web.errors import ImageInvalid, ValidationFailed
from app.web.ratelimit import rate_limit

FORM_OVERHEAD_BYTES = 64 * 1024
MAX_BODY_BYTES = MAX_IMAGE_BYTES + FORM_OVERHEAD_BYTES

MultiPartParser.spool_max_size = MAX_BODY_BYTES

PayloadT = TypeVar("PayloadT", bound=BaseModel)

router = APIRouter(tags=["AGT · travel agent"])


@router.post(
    "/agent/ask",
    summary="여행 탭 질의 — 자유문·사진 → 단계 + 답변 + 스팟",
    dependencies=[Depends(rate_limit(bucket="agent_ask", limit=20, window_seconds=60))],
)
async def agent_ask(
    request: Request, session: DbSession, redis: RedisDep, kto: KtoDep
) -> dict[str, Any]:
    payload, image_bytes, image_mime = await _read_payload(request)
    result = await ask_service.ask(
        session,
        redis,
        kto,
        question=payload.question,
        lat=payload.lat,
        lng=payload.lng,
        image_bytes=image_bytes,
        image_mime=image_mime,
        intent=payload.intent,
        patch=payload.patch,
        anchor=payload.anchor,
        context=payload.context,
    )
    return ok(result)


@router.post(
    "/agent/chat",
    summary="여행 탭 채팅 — 자유문·사진 → SSE 스트리밍 답변",
    dependencies=[Depends(rate_limit(bucket="agent_chat", limit=10, window_seconds=60))],
)
async def agent_chat(
    request: Request, session: DbSession, redis: RedisDep, kto: KtoDep
) -> StreamingResponse:
    fields, image_bytes, image_mime = await _read_fields(request)
    payload = _parse(fields, ChatRequest, label="chat")
    return StreamingResponse(
        chat_service.stream(
            session,
            redis,
            kto,
            payload=payload,
            image_bytes=image_bytes,
            image_mime=image_mime,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/agent/mood-images",
    summary="분위기별 대표 사진 — 여행 탭 시작 화면 타일",
    dependencies=[Depends(rate_limit(bucket="agent_moods", limit=30, window_seconds=60))],
)
async def agent_mood_images(session: DbSession) -> dict[str, Any]:
    return ok(await moods_service.mood_images(session))


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
    fields, image_bytes, image_mime = await _read_fields(request)
    return _parse(fields, AskRequest, label="ask"), image_bytes, image_mime


async def _read_fields(request: Request) -> tuple[dict[str, Any], bytes | None, str | None]:
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
        for key in ("intent", "patch", "anchor", "context", "history"):
            raw = fields.get(key)
            if isinstance(raw, str):
                try:
                    fields[key] = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValidationFailed(f"invalid {key} json") from exc
        return fields, image_bytes, image_mime
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationFailed("invalid json body") from exc
    if not isinstance(body, dict):
        raise ValidationFailed("body must be an object")
    return body, None, None


def _parse(raw: dict[str, Any], model: type[PayloadT], *, label: str) -> PayloadT:
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise ValidationFailed(f"invalid {label} payload") from exc


async def _read_capped(upload: UploadFile) -> bytes:
    payload = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(payload) > MAX_IMAGE_BYTES:
        raise ImageInvalid()
    return payload
