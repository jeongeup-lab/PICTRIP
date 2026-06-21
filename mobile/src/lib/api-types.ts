/**
 * Mirrors backend/app/core/schemas.py — keep in sync (JSend envelope).
 */

export interface ResponseMeta {
  traceId: string;
}

export interface ErrorPayload {
  code: string;
  message: string;
}

export interface Envelope<T> {
  data: T | null;
  error: ErrorPayload | null;
  meta: ResponseMeta;
}

// Canonical card core — { contentId, title, firstImageUrl, category }
export interface SpotCard {
  contentId: string;
  title: string;
  firstImageUrl: string | null;
  category: string;
}
