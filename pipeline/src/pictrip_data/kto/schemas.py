"""KTO response parsing DTOs."""

from __future__ import annotations

from pydantic import BaseModel


class KtoSpot(BaseModel):
    """Subset of areaBasedSyncList2 item fields used for the spots upsert."""

    content_id: str
    title: str
    # TODO: mapx, mapy, first_image_url, area/sigungu codes, show_flag, lcls_systm*, modified_time
