import { api } from "@/lib/api-client";

export type RegionFilter =
  | "all"
  | "capital"
  | "gangwon"
  | "chungcheong"
  | "jeolla"
  | "gyeongsang"
  | "jeju";
export type WhenFilter = "any" | "today" | "weekend" | "next_week";
export type WhoFilter = "any" | "solo" | "duo" | "kids" | "pets";

export interface Conditions {
  region: RegionFilter;
  when: WhenFilter;
  who: WhoFilter;
}

export const DEFAULT_CONDITIONS: Conditions = { region: "all", when: "any", who: "any" };

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
  tag: string | null;
  lat: number | null;
  lng: number | null;
}

export interface AgentAnswer {
  steps: AgentStep[];
  answer: AnswerPart[];
  spots: TravelSpot[];
  totalCount: number;
  suggestions: string[];
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

export interface AskInput {
  question: string;
  photo?: PhotoUpload | null;
  conditions: Conditions;
  coords?: Coords | null;
}

const ASK_TIMEOUT_MS = 60_000;

function askForm(input: AskInput, photo: PhotoUpload): FormData {
  const form = new FormData();
  form.append("photo", photo as unknown as Blob);
  form.append("question", input.question);
  form.append("region", input.conditions.region);
  form.append("when", input.conditions.when);
  form.append("who", input.conditions.who);
  if (input.coords) {
    form.append("lat", String(input.coords.lat));
    form.append("lng", String(input.coords.lng));
  }
  return form;
}

function askBody(input: AskInput): Record<string, string | number> {
  const body: Record<string, string | number> = {
    question: input.question,
    region: input.conditions.region,
    when: input.conditions.when,
    who: input.conditions.who,
  };
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
