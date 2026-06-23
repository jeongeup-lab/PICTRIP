/** Single-select map category chips. Values are 1:1 with the backend
 * NearbyCategory enum (spots/services/nearby.py); 전체 omits the param. */
export type NearbyCategory = "attraction" | "food" | "cafe" | "leisure" | "shopping";

export interface CategoryChip {
  label: string;
  value: NearbyCategory | null;
}

export const CATEGORY_CHIPS: CategoryChip[] = [
  { label: "전체", value: null },
  { label: "관광지", value: "attraction" },
  { label: "음식점", value: "food" },
  { label: "카페", value: "cafe" },
  { label: "레저", value: "leisure" },
  { label: "쇼핑", value: "shopping" },
];
