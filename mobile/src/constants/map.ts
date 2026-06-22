/** Seoul City Hall — degraded map center when GPS is unavailable (S05 §0). */
export const SEOUL_CITY_HALL = { lat: 37.5666, lng: 126.9784 } as const;

/** Fixed query radius in metres (S05 §0; no UI control). */
export const RADIUS_M = 3000;

/** Max nearby cards rendered (S05 §0). */
export const NEARBY_CAP = 30;

/** "이 지역에서 검색" appears once the viewport drifts this fraction of the
 * radius from the last query center (S05 §1.4 ~30%). */
export const SEARCH_HERE_RATIO = 0.3;
