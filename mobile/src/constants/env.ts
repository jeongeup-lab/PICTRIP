// Fallback MUST include the /v1 prefix — every backend API lives under /v1, so a
// build that fails to inline EXPO_PUBLIC_API_BASE (e.g. .env not loaded) would
// otherwise 404 on every request. See fix/mobile-api-base-v1-compat (2026-07).
export const API_BASE = process.env.EXPO_PUBLIC_API_BASE ?? "https://api.pictrip.org/v1";
export const KAKAO_JS_KEY = process.env.EXPO_PUBLIC_KAKAO_JS_KEY ?? "";
