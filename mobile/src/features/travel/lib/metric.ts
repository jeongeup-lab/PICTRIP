import type { IconName } from "@/components/Icon";

export interface Metric {
  icon: IconName;
  label: string;
  tooltip: string;
}

const DISTANCE = /^[\d.]+(km|m)$/;
const CROWD = /^(한산|보통|붐빔|하위 \d+%)$/;
const DDAY = /^D-\d+$/;
const PHOTO_PREFIX = "유사도 ";
const CROWD_FALLBACK = "혼잡도 예측 기준";
const PHOTO_FALLBACK = "사진 유사도 기준";
const FESTIVAL_BASIS = "축제 기간 기준";

export function isDistanceTag(tag: string | null | undefined): boolean {
  return typeof tag === "string" && DISTANCE.test(tag);
}

export function metricOf(
  tag: string | null | undefined,
  tagBasis: string | null | undefined,
): Metric | null {
  if (!tag) return null;
  if (isDistanceTag(tag)) return null;
  if (CROWD.test(tag)) {
    return { icon: "users", label: tag, tooltip: tagBasis ?? CROWD_FALLBACK };
  }
  if (tag.startsWith(PHOTO_PREFIX)) {
    return { icon: "image", label: tag, tooltip: tagBasis ?? PHOTO_FALLBACK };
  }
  if (DDAY.test(tag)) {
    return { icon: "calendar", label: tag, tooltip: FESTIVAL_BASIS };
  }
  return { icon: "tag", label: tag, tooltip: "" };
}
