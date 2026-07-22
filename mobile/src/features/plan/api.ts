import { api } from "@/lib/api-client";

export type PlaceType = "attraction" | "restaurant" | "cafe" | "hotel" | "region";
export type ResolveStatus = "matched" | "ambiguous" | "naver_only" | "unmatched";
export type SourceKind = "text" | "youtube" | "image" | "photo";
export type TimeOfDay = "morning" | "afternoon" | "evening";

export type ExtractedPlace = {
  name: string;
  nameKo: string | null;
  placeType: PlaceType;
  regionHint: string | null;
  tip: string | null;
  orderHint: number | null;
};

export type ResolvedSpot = {
  source: "kto" | "naver";
  contentId: string | null;
  title: string;
  category: string | null;
  address: string | null;
  lat: number | null;
  lng: number | null;
  imageUrl: string | null;
};

export type ResolvedPlace = {
  extracted: ExtractedPlace;
  spot: ResolvedSpot | null;
  confidence: number;
  status: ResolveStatus;
};

export type ImportResult = {
  sourceKind: SourceKind;
  sourceTitle: string | null;
  tripDays: number | null;
  places: ResolvedPlace[];
};

export type ScheduleSlot = {
  timeOfDay: TimeOfDay;
  place: ResolvedPlace;
  travelMinutesFromPrev: number | null;
};

export type ScheduleDay = {
  day: number;
  regionLabel: string | null;
  slots: ScheduleSlot[];
};

export type Plan = {
  planId: string | null;
  sourceTitle: string | null;
  sourceUrl: string | null;
  days: ScheduleDay[];
  unplaced: ResolvedPlace[];
};

export type PhotoMatch = {
  contentId: string;
  title: string;
  category: string | null;
  address: string | null;
  lat: number | null;
  lng: number | null;
  imageUrl: string | null;
  similarity: number;
};

export type AssembleBody = {
  places: ResolvedPlace[];
  days: number | null;
  sourceKind: SourceKind;
  sourceUrl: string | null;
  sourceTitle: string | null;
};

export type PlanEdit =
  | { op: "remove"; day: number; slot: number }
  | { op: "replace"; day: number; slot: number; contentId: string };

export type PhotoUpload = { uri: string; name: string; type: string };

const EXTRACTION_TIMEOUT_MS = 180_000;
const ASSEMBLE_TIMEOUT_MS = 60_000;

const multipart = (timeout: number) => ({
  headers: { "Content-Type": "multipart/form-data" },
  timeout,
});

function imageForm(photo: PhotoUpload): FormData {
  const form = new FormData();
  form.append("image", photo as unknown as Blob);
  return form;
}

export async function importContent(source: {
  url?: string;
  text?: string;
}): Promise<ImportResult> {
  return (await api.post("/plan/import", source, {
    timeout: EXTRACTION_TIMEOUT_MS,
  })) as unknown as ImportResult;
}

export async function importImage(photo: PhotoUpload): Promise<ImportResult> {
  return (await api.post(
    "/plan/import",
    imageForm(photo),
    multipart(EXTRACTION_TIMEOUT_MS),
  )) as unknown as ImportResult;
}

export async function matchPhoto(photo: PhotoUpload): Promise<PhotoMatch[]> {
  const result = (await api.post(
    "/plan/photo-match",
    imageForm(photo),
    multipart(ASSEMBLE_TIMEOUT_MS),
  )) as unknown as { matches: PhotoMatch[] };
  return result.matches;
}

export async function assemblePlan(body: AssembleBody): Promise<Plan> {
  return (await api.post("/plan/assemble", body, {
    timeout: ASSEMBLE_TIMEOUT_MS,
  })) as unknown as Plan;
}

export async function planFromSpot(contentId: string, days: number): Promise<Plan> {
  return (await api.post(
    "/plan/from-spot",
    { contentId, days },
    { timeout: ASSEMBLE_TIMEOUT_MS },
  )) as unknown as Plan;
}

export async function getPlan(planId: string): Promise<Plan> {
  return (await api.get(`/plan/${planId}`)) as unknown as Plan;
}

export async function getAlternatives(
  planId: string,
  day: number,
  slot: number,
): Promise<ResolvedSpot[]> {
  const result = (await api.get(`/plan/${planId}/alternatives`, {
    params: { day, slot },
    timeout: ASSEMBLE_TIMEOUT_MS,
  })) as unknown as { alternatives: ResolvedSpot[] };
  return result.alternatives;
}

export async function editPlan(planId: string, edit: PlanEdit): Promise<Plan> {
  return (await api.patch(`/plan/${planId}`, edit, {
    timeout: ASSEMBLE_TIMEOUT_MS,
  })) as unknown as Plan;
}
