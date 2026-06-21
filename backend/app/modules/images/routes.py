"""IMG routes — admin-only. Public IMG flow goes through TST /taste/photo-search."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.core.schemas import ok

router = APIRouter(tags=["IMG · image/matching (admin)"])


@router.get(
    "/admin/embeddings/status",
    status_code=status.HTTP_200_OK,
    summary="(WIP) embedding load status",
)
async def embeddings_status() -> dict[str, Any]:
    # TODO: count(spot_embeddings) vs count(spots)
    return ok({"placeholder": "IMG-001"})
