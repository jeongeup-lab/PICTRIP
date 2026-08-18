import { create } from "zustand";
import type {
  AskContext,
  ChatCardsEvent,
  ChatDoneEvent,
  ChatHistoryItem,
  ChatStepEvent,
  PhotoUpload,
  QueryIntent,
  RefinePatch,
  SourceItem,
  Suggestion,
  TravelSpot,
} from "@/features/travel/api";

export type ChatTurnStatus = "streaming" | "done" | "error";

export interface ChatStep {
  index: number;
  label: string;
  badge: string | null;
  status: "run" | "done";
}

export interface ChatRequestSeed {
  message: string | null;
  photo: PhotoUpload | null;
  context: AskContext | null;
  intent: QueryIntent | null;
  patch: RefinePatch | null;
  history: ChatHistoryItem[];
}

export interface ChatTurn {
  id: string;
  question: string;
  photoUri: string | null;
  request: ChatRequestSeed;
  status: ChatTurnStatus;
  steps: ChatStep[];
  text: string;
  spots: TravelSpot[];
  tagBasis: string | null;
  applied: string[];
  refinements: Suggestion[];
  sources: SourceItem[];
  intent: QueryIntent | null;
  errorCode: string | null;
}

export const HISTORY_LIMIT = 8;
export const HISTORY_TEXT_LIMIT = 300;

export function historyOf(turns: ChatTurn[]): ChatHistoryItem[] {
  const items: ChatHistoryItem[] = [];
  for (const turn of turns) {
    items.push({ role: "user", text: turn.question });
    if (turn.status === "done") {
      items.push({
        role: "assistant",
        text: turn.text.slice(0, HISTORY_TEXT_LIMIT),
        spotIds: turn.spots.map((spot) => spot.contentId),
      });
    }
  }
  return items.slice(-HISTORY_LIMIT);
}

export function lastDoneTurn(turns: ChatTurn[]): ChatTurn | null {
  for (let i = turns.length - 1; i >= 0; i -= 1) {
    if (turns[i].status === "done") return turns[i];
  }
  return null;
}

interface ChatState {
  turns: ChatTurn[];
  streaming: boolean;
  activeId: string | null;
  issued: number;
  nextTurnId: () => string;
  begin: (turn: {
    id: string;
    question: string;
    photoUri: string | null;
    request: ChatRequestSeed;
  }) => void;
  applyStep: (id: string, step: ChatStepEvent) => void;
  appendDelta: (id: string, text: string) => void;
  setCards: (id: string, event: ChatCardsEvent) => void;
  setSources: (id: string, sources: SourceItem[]) => void;
  finish: (id: string, done: ChatDoneEvent) => void;
  fail: (id: string, errorCode: string) => void;
  retry: (id: string) => void;
  clear: () => void;
}

function freshBody(): Pick<
  ChatTurn,
  | "status"
  | "steps"
  | "text"
  | "spots"
  | "tagBasis"
  | "applied"
  | "refinements"
  | "sources"
  | "intent"
  | "errorCode"
> {
  return {
    status: "streaming",
    steps: [],
    text: "",
    spots: [],
    tagBasis: null,
    applied: [],
    refinements: [],
    sources: [],
    intent: null,
    errorCode: null,
  };
}

function patchTurn(turns: ChatTurn[], id: string, next: Partial<ChatTurn>): ChatTurn[] {
  return turns.map((turn) => (turn.id === id ? { ...turn, ...next } : turn));
}

function upsertStep(steps: ChatStep[], event: ChatStepEvent): ChatStep[] {
  const next: ChatStep = {
    index: event.index,
    label: event.label,
    badge: event.badge ?? null,
    status: event.status,
  };
  const at = steps.findIndex((step) => step.index === event.index);
  if (at < 0) return [...steps, next];
  return steps.map((step, i) => (i === at ? next : step));
}

export const useChat = create<ChatState>((set, get) => ({
  turns: [],
  streaming: false,
  activeId: null,
  issued: 0,
  nextTurnId: () => {
    const issued = get().issued + 1;
    set({ issued });
    return `turn-${issued}`;
  },
  begin: ({ id, question, photoUri, request }) =>
    set((s) => ({
      streaming: true,
      activeId: id,
      turns: [...s.turns, { id, question, photoUri, request, ...freshBody() }],
    })),
  applyStep: (id, step) =>
    set((s) =>
      s.activeId === id
        ? {
            turns: s.turns.map((turn) =>
              turn.id === id ? { ...turn, steps: upsertStep(turn.steps, step) } : turn,
            ),
          }
        : s,
    ),
  appendDelta: (id, text) =>
    set((s) =>
      s.activeId === id
        ? {
            turns: s.turns.map((turn) =>
              turn.id === id ? { ...turn, text: turn.text + text } : turn,
            ),
          }
        : s,
    ),
  setCards: (id, event) =>
    set((s) =>
      s.activeId === id
        ? {
            turns: patchTurn(s.turns, id, {
              spots: event.spots,
              tagBasis: event.tagBasis ?? null,
              applied: event.applied ?? [],
              refinements: event.refinements ?? [],
            }),
          }
        : s,
    ),
  setSources: (id, sources) =>
    set((s) => (s.activeId === id ? { turns: patchTurn(s.turns, id, { sources }) } : s)),
  finish: (id, done) =>
    set((s) =>
      s.activeId === id
        ? {
            streaming: false,
            activeId: null,
            turns: s.turns.map((turn) =>
              turn.id === id
                ? {
                    ...turn,
                    status: "done",
                    text: done.answerText,
                    spots: done.spots,
                    sources: done.sources,
                    intent: done.intent,
                    applied: done.applied ?? turn.applied,
                    refinements: done.refinements ?? turn.refinements,
                    steps: turn.steps.map((step) => ({ ...step, status: "done" })),
                  }
                : turn,
            ),
          }
        : s,
    ),
  fail: (id, errorCode) =>
    set((s) =>
      s.activeId === id
        ? {
            streaming: false,
            activeId: null,
            turns: patchTurn(s.turns, id, { status: "error", errorCode }),
          }
        : s,
    ),
  retry: (id) =>
    set((s) => ({
      streaming: true,
      activeId: id,
      turns: s.turns.map((turn) => (turn.id === id ? { ...turn, ...freshBody() } : turn)),
    })),
  clear: () => set({ turns: [], streaming: false, activeId: null }),
}));
