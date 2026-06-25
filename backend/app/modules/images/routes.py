"""IMG routes. Empty router (no endpoints yet); public image flow is served by TST /taste/photo-search."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["IMG · image/matching (admin)"])
