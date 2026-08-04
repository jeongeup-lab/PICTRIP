import { create } from "zustand";
import type {
  AgentAnswer,
  AskAnchor,
  PhotoUpload,
  QueryIntent,
  RefinePatch,
} from "@/features/travel/api";

export type TurnStatus = "pending" | "done" | "failed";

export interface Turn {
  id: string;
  question: string;
  request: string;
  photo: PhotoUpload | null;
  intent: QueryIntent | null;
  patch: RefinePatch | null;
  anchor: AskAnchor | null;
  status: TurnStatus;
  answer: AgentAnswer | null;
  errorMessage: string | null;
}

interface ConversationState {
  turns: Turn[];
  busy: boolean;
  activeId: string | null;
  start: (turn: {
    id: string;
    question: string;
    request: string;
    photo: PhotoUpload | null;
    intent?: QueryIntent | null;
    patch?: RefinePatch | null;
    anchor?: AskAnchor | null;
  }) => void;
  retry: (id: string) => void;
  resolve: (id: string, answer: AgentAnswer) => void;
  fail: (id: string, errorMessage: string) => void;
  clear: () => void;
}

function patch(turns: Turn[], id: string, next: Partial<Turn>): Turn[] {
  return turns.map((t) => (t.id === id ? { ...t, ...next } : t));
}

export const useConversation = create<ConversationState>((set) => ({
  turns: [],
  busy: false,
  activeId: null,
  start: ({ id, question, request, photo, intent = null, patch = null, anchor = null }) =>
    set((s) => ({
      busy: true,
      activeId: id,
      turns: [
        ...s.turns,
        {
          id,
          question,
          request,
          photo,
          intent,
          patch,
          anchor,
          status: "pending",
          answer: null,
          errorMessage: null,
        },
      ],
    })),
  retry: (id) =>
    set((s) => ({
      busy: true,
      activeId: id,
      turns: patch(s.turns, id, { status: "pending", errorMessage: null }),
    })),
  resolve: (id, answer) =>
    set((s) =>
      s.activeId === id
        ? { busy: false, activeId: null, turns: patch(s.turns, id, { status: "done", answer }) }
        : s,
    ),
  fail: (id, errorMessage) =>
    set((s) =>
      s.activeId === id
        ? {
            busy: false,
            activeId: null,
            turns: patch(s.turns, id, { status: "failed", errorMessage }),
          }
        : s,
    ),
  clear: () => set({ turns: [], busy: false, activeId: null }),
}));
