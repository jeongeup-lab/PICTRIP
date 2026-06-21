"""REC DTOs.

The `/recommendations/today-inspo` route serialises an inline dict
(`{contentId, title, firstImageUrl, addr1, mapx, mapy}`, validated by
`test_rec_today_inspo_routes`). A stale `TodayInspo` model with a different
shape (`id`/`imageUrl`/`reason`) used to live here and was never imported —
removed to avoid implying a contract the route does not serve. Real DTOs land
when REC-004 ("why this place?") is implemented.
"""

from __future__ import annotations
