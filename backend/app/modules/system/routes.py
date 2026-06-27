"""SYS routes. Endpoints mirror API spec §12."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.config import settings
from app.core.schemas import ok
from app.core.version import API_VERSION

router = APIRouter(tags=["SYS · system/meta"])


@router.get("/meta/version", status_code=status.HTTP_200_OK, summary="API version/meta")
async def version() -> dict[str, Any]:
    return ok(
        {
            "apiVersion": API_VERSION,
            "environment": settings.ENVIRONMENT,
            "ktoApiStatus": "unknown",
        }
    )
