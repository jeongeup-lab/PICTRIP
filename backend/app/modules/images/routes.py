"""IMG routes — admin-only. Public IMG flow goes through TST /taste/photo-search.

No HTTP endpoints are currently exposed: the public image flow is served by TST
(``/taste/photo-search``) and the admin embedding-status view is not yet built.
The (empty) router is still mounted by ``app.main`` so the IMG seam stays wired
for when admin endpoints land.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["IMG · image/matching (admin)"])
