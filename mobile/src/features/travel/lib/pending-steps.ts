import type { AgentStep } from "@/features/travel/api";

export const UNDERSTAND_STEP: AgentStep = {
  tool: "intent",
  label: "질문에서 조건 읽는 중",
  badge: null,
};

export const SEARCH_STEP: AgentStep = {
  tool: "search",
  label: "여행지 찾는 중",
  badge: null,
};

export interface PendingShape {
  request: string;
  intent: unknown | null;
  anchor: unknown | null;
}

export function extractsIntent({ request, intent, anchor }: PendingShape): boolean {
  return anchor === null && intent === null && request.trim().length > 0;
}

export function pendingSteps(shape: PendingShape): AgentStep[] {
  return extractsIntent(shape) ? [UNDERSTAND_STEP, SEARCH_STEP] : [SEARCH_STEP];
}
