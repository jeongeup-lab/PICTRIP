import { fetch as expoFetch } from "expo/fetch";
import { API_BASE } from "@/constants/env";
import { AppError } from "@/lib/app-error";
import { envelopeToError } from "@/lib/jsend";
import { getAuthSession } from "@/lib/auth-session";
import { readSseStream } from "@/features/travel/lib/sse";
import type { Envelope } from "@/lib/api-types";

export type CrowdPreference = "quiet" | "any" | "popular";
export type Mood = "sea" | "mountain" | "lake" | "island" | "hanok" | "night" | "street";
export type DropAxis = "crowd" | "indoor" | "near" | "region" | "category";

export interface ExtractedPlace {
  name: string;
  nameKo?: string | null;
  placeType?: string;
  regionHint?: string | null;
}

export type TaskKind = "search" | "detail" | "smalltalk" | "unsupported";

export interface QueryIntent {
  task?: TaskKind;
  categoryKeywords: string[];
  regionHints: string[];
  namedPlaces?: ExtractedPlace[];
  moodHints?: Mood[];
  crowdPreference?: CrowdPreference;
  indoorOnly?: boolean;
  nearMe?: boolean;
  festivalOnly?: boolean;
  outOfScope?: boolean;
}

export interface RefinePatch {
  crowdPreference?: CrowdPreference;
  indoorOnly?: boolean;
  nearMe?: boolean;
  drop?: DropAxis;
}

export interface Suggestion {
  label: string;
  patch: RefinePatch;
}

export interface TravelSpot {
  contentId: string;
  title: string;
  regionLabel: string;
  imageUrl: string | null;
  fallbackImageUrl?: string | null;
  tag: string | null;
  lat: number | null;
  lng: number | null;
  categoryGroup?: string | null;
  chips?: string[];
  hasCrowd?: boolean;
  source?: "kto" | "kakao";
  externalUrl?: string | null;
  phone?: string | null;
  distanceM?: number | null;
  saveable?: boolean;
}

export interface PhotoUpload {
  uri: string;
  name: string;
  type: string;
}

export interface Coords {
  lat: number;
  lng: number;
}

export interface AskContextSpot {
  contentId: string;
  title: string;
}

export interface AskContext {
  intent?: QueryIntent | null;
  spots: AskContextSpot[];
  focusContentId?: string;
}

export type SourceKind = "naver_blog" | "kto" | "kakao";

export interface SourceItem {
  kind: SourceKind;
  title: string;
  url?: string | null;
  date?: string | null;
}

export interface ChatHistoryItem {
  role: "user" | "assistant";
  text: string;
  spotIds?: string[];
}

export interface ChatStepEvent {
  index: number;
  label: string;
  badge?: string | null;
  status: "run" | "done";
}

export interface ChatCardsEvent {
  spots: TravelSpot[];
  tagBasis?: string | null;
  applied?: string[];
  refinements?: Suggestion[];
}

export interface ChatDoneEvent {
  answerText: string;
  spots: TravelSpot[];
  sources: SourceItem[];
  intent: QueryIntent;
  totalCount: number;
  applied?: string[];
  refinements?: Suggestion[];
  traceId?: string | null;
}

export interface ChatErrorEvent {
  code: string;
  message: string;
}

export interface ChatInput {
  message: string | null;
  photo?: PhotoUpload | null;
  coords?: Coords | null;
  clientTime?: string | null;
  context?: AskContext | null;
  intent?: QueryIntent | null;
  patch?: RefinePatch | null;
  history?: ChatHistoryItem[] | null;
}

export interface ChatHandlers {
  onStep?: (event: ChatStepEvent) => void;
  onDelta?: (text: string) => void;
  onCards?: (event: ChatCardsEvent) => void;
  onSources?: (items: SourceItem[]) => void;
  onDone?: (event: ChatDoneEvent) => void;
  onError?: (event: ChatErrorEvent) => void;
}

function chatBody(input: ChatInput): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (input.message) body.message = input.message;
  if (input.coords) {
    body.lat = input.coords.lat;
    body.lng = input.coords.lng;
  }
  if (input.clientTime) body.clientTime = input.clientTime;
  if (input.context) body.context = input.context;
  if (input.intent) body.intent = input.intent;
  if (input.patch) body.patch = input.patch;
  if (input.history && input.history.length > 0) body.history = input.history;
  return body;
}

function chatForm(input: ChatInput, photo: PhotoUpload): FormData {
  const form = new FormData();
  form.append("photo", photo as unknown as Blob);
  if (input.message) form.append("message", input.message);
  if (input.coords) {
    form.append("lat", String(input.coords.lat));
    form.append("lng", String(input.coords.lng));
  }
  if (input.clientTime) form.append("clientTime", input.clientTime);
  if (input.context) form.append("context", JSON.stringify(input.context));
  if (input.history && input.history.length > 0)
    form.append("history", JSON.stringify(input.history));
  return form;
}

function dispatchChatEvent(name: string, data: string, handlers: ChatHandlers): void {
  let payload: unknown;
  try {
    payload = JSON.parse(data);
  } catch {
    return;
  }
  if (payload === null || typeof payload !== "object") return;
  if (name === "step") handlers.onStep?.(payload as ChatStepEvent);
  else if (name === "delta") handlers.onDelta?.((payload as { text: string }).text ?? "");
  else if (name === "cards") handlers.onCards?.(payload as ChatCardsEvent);
  else if (name === "sources")
    handlers.onSources?.((payload as { items: SourceItem[] }).items ?? []);
  else if (name === "done") handlers.onDone?.(payload as ChatDoneEvent);
  else if (name === "error") handlers.onError?.(payload as ChatErrorEvent);
}

export async function streamChat(
  input: ChatInput,
  handlers: ChatHandlers,
  signal?: AbortSignal | null,
): Promise<void> {
  const headers: Record<string, string> = { Accept: "text/event-stream" };
  const token = getAuthSession()?.getAccessToken() ?? null;
  if (token) headers.Authorization = `Bearer ${token}`;
  const photo = input.photo ?? null;
  let body: BodyInit;
  if (photo) {
    body = chatForm(input, photo);
  } else {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(chatBody(input));
  }

  let response;
  try {
    response = await expoFetch(`${API_BASE}/agent/chat`, {
      method: "POST",
      headers,
      body,
      signal: signal ?? null,
    });
  } catch {
    if (signal?.aborted) return;
    throw new AppError("NETWORK_ERROR", "네트워크에 연결할 수 없습니다.", 0);
  }

  if (!response.ok) {
    let envelope: Envelope<unknown> | null = null;
    try {
      envelope = (await response.json()) as Envelope<unknown>;
    } catch {
      envelope = null;
    }
    if (envelope) throw envelopeToError(envelope, response.status);
    throw new AppError("UNKNOWN", "Unexpected error.", response.status);
  }

  const stream = response.body;
  if (!stream) throw new AppError("NETWORK_ERROR", "네트워크에 연결할 수 없습니다.", 0);

  await readSseStream(
    stream,
    (event) => dispatchChatEvent(event.event, event.data, handlers),
    signal,
  );
}
