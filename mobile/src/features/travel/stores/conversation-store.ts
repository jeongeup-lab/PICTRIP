import { create } from "zustand";
import type { AgentAnswer, PhotoUpload, QueryIntent, RefinePatch } from "@/features/travel/api";

export type TurnStatus = "pending" | "playing" | "done" | "failed";

export interface Turn {
  id: string;
  question: string;
  request: string;
  photo: PhotoUpload | null;
  intent: QueryIntent | null;
  patch: RefinePatch | null;
  status: TurnStatus;
  answer: AgentAnswer | null;
  errorMessage: string | null;
}

interface ConversationState {
  turns: Turn[];
  busy: boolean;
  start: (turn: {
    id: string;
    question: string;
    request: string;
    photo: PhotoUpload | null;
    intent?: QueryIntent | null;
    patch?: RefinePatch | null;
  }) => void;
  retry: (id: string) => void;
  resolve: (id: string, answer: AgentAnswer) => void;
  fail: (id: string, errorMessage: string) => void;
  finishPlayback: (id: string) => void;
  clear: () => void;
}

function patch(turns: Turn[], id: string, next: Partial<Turn>): Turn[] {
  return turns.map((t) => (t.id === id ? { ...t, ...next } : t));
}

export const useConversation = create<ConversationState>((set) => ({
  turns: [],
  busy: false,
  start: ({ id, question, request, photo, intent = null, patch = null }) =>
    set((s) => ({
      busy: true,
      turns: [
        ...s.turns,
        {
          id,
          question,
          request,
          photo,
          intent,
          patch,
          status: "pending",
          answer: null,
          errorMessage: null,
        },
      ],
    })),
  retry: (id) =>
    set((s) => ({
      busy: true,
      turns: patch(s.turns, id, { status: "pending", errorMessage: null }),
    })),
  resolve: (id, answer) =>
    set((s) => ({ turns: patch(s.turns, id, { status: "playing", answer }) })),
  fail: (id, errorMessage) =>
    set((s) => ({ busy: false, turns: patch(s.turns, id, { status: "failed", errorMessage }) })),
  finishPlayback: (id) =>
    set((s) => ({ busy: false, turns: patch(s.turns, id, { status: "done" }) })),
  clear: () => set({ turns: [], busy: false }),
}));
