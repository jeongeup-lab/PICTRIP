from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from starlette.datastructures import UploadFile

from app.core.db import DbSession
from app.kto.client import KtoDep
from app.modules.plan.errors import PlanSourceInvalid
from app.modules.plan.schemas import AssembleRequest, ImportResponse
from app.modules.plan.services import assemble, extract, ingest, resolve
from app.web.envelope import ok

router = APIRouter(tags=["plan"])


@router.post("/plan/import")
async def import_content(request: Request, session: DbSession, kto: KtoDep) -> dict[str, Any]:
    text, url, image_bytes, image_mime = await _read_import_payload(request)
    source = await ingest.normalize(
        text=text, url=url, image_bytes=image_bytes, image_mime=image_mime
    )
    extraction = await extract.extract_places(source)
    places = await resolve.resolve_places(session, kto, extraction.places)
    return ok(
        ImportResponse(
            sourceKind=source.kind,
            sourceTitle=source.source_title,
            tripDays=extraction.trip_days,
            places=places,
        )
    )


@router.post("/plan/assemble")
async def assemble_plan(session: DbSession, payload: AssembleRequest) -> dict[str, Any]:
    plan = await assemble.build_schedule(session, payload)
    return ok(plan)


@router.get("/plan/{plan_id}")
async def get_plan(session: DbSession, plan_id: int) -> dict[str, Any]:
    plan = await assemble.load_plan(session, plan_id)
    return ok(plan)


async def _read_import_payload(
    request: Request,
) -> tuple[str | None, str | None, bytes | None, str | None]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/"):
        form = await request.form()
        upload = form.get("image")
        text = form.get("text")
        url = form.get("url")
        image_bytes = None
        image_mime = None
        if isinstance(upload, UploadFile):
            image_bytes = await upload.read()
            image_mime = upload.content_type
        return (
            text if isinstance(text, str) else None,
            url if isinstance(url, str) else None,
            image_bytes or None,
            image_mime,
        )
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PlanSourceInvalid() from exc
    if not isinstance(body, dict):
        raise PlanSourceInvalid()
    text = body.get("text")
    url = body.get("url")
    return (
        text if isinstance(text, str) else None,
        url if isinstance(url, str) else None,
        None,
        None,
    )
