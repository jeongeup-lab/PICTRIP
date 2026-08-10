import { api } from "@/lib/api-client";

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

export type AnchorAction = "food" | "cafe" | "nearby" | "crowd" | "related";

export interface AskAnchor {
  contentId?: string;
  action: AnchorAction;
}

export interface AgentStep {
  tool: string;
  label: string;
  badge: string | null;
}

export interface AnswerPart {
  text: string;
  emphasis: boolean;
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
  hasCrowd?: boolean;
}

export interface AgentAnswer {
  steps: AgentStep[];
  answer: AnswerPart[];
  spots: TravelSpot[];
  totalCount: number;
  intent: QueryIntent;
  tagBasis?: string | null;
  suggestions: string[];
  refinements?: Suggestion[];
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

export interface AskInput {
  question?: string;
  photo?: PhotoUpload | null;
  intent?: QueryIntent | null;
  patch?: RefinePatch | null;
  anchor?: AskAnchor | null;
  context?: AskContext | null;
  coords?: Coords | null;
}

const ASK_TIMEOUT_MS = 60_000;

function askForm(input: AskInput, photo: PhotoUpload): FormData {
  const form = new FormData();
  form.append("photo", photo as unknown as Blob);
  if (input.question) form.append("question", input.question);
  if (input.intent) form.append("intent", JSON.stringify(input.intent));
  if (input.patch) form.append("patch", JSON.stringify(input.patch));
  if (input.anchor) form.append("anchor", JSON.stringify(input.anchor));
  if (input.context) form.append("context", JSON.stringify(input.context));
  if (input.coords) {
    form.append("lat", String(input.coords.lat));
    form.append("lng", String(input.coords.lng));
  }
  return form;
}

function askBody(input: AskInput): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (input.question) body.question = input.question;
  if (input.intent) body.intent = input.intent;
  if (input.patch) body.patch = input.patch;
  if (input.anchor) body.anchor = input.anchor;
  if (input.context) body.context = input.context;
  if (input.coords) {
    body.lat = input.coords.lat;
    body.lng = input.coords.lng;
  }
  return body;
}

export async function askAgent(input: AskInput): Promise<AgentAnswer> {
  const photo = input.photo ?? null;
  if (photo) {
    return (await api.post("/agent/ask", askForm(input, photo), {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: ASK_TIMEOUT_MS,
    })) as unknown as AgentAnswer;
  }
  return (await api.post("/agent/ask", askBody(input), {
    timeout: ASK_TIMEOUT_MS,
  })) as unknown as AgentAnswer;
}
