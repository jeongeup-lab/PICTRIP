import { create } from "zustand";
import { postChatTurn } from "@/features/chat/api";
import type { ChatAnswer, ChatBoard, ChatEntry, ChatTurnResponse } from "@/features/chat/types";

type StorePhase = "refining" | "converged" | "empty" | "done";

interface ChatState {
  sessionId: string | null;
  phase: StorePhase;
  poolTotal: number | null;
  candidateCount: number | null;
  entries: ChatEntry[];
  pending: boolean;
  send: (utterance: string) => Promise<void>;
  pickAnswer: (answer: ChatAnswer) => Promise<void>;
  removeCondition: (id: string) => Promise<void>;
  commit: () => void;
  reset: () => void;
}

let seq = 0;
const nextId = (): string => `e${++seq}`;

const ERROR_TEXT = "응답을 만들지 못했어요. 잠시 후 다시 보내 주세요.";

function boardOf(res: ChatTurnResponse): ChatBoard {
  return {
    round: res.round,
    phase: res.phase,
    poolTotal: res.poolTotal,
    candidateCount: res.candidateCount,
    conditions: res.conditions,
    question: res.question,
    answers: res.answers,
  };
}

function latestBoardEntry(entries: ChatEntry[]): ChatEntry | undefined {
  for (let i = entries.length - 1; i >= 0; i -= 1) {
    if (entries[i].board) return entries[i];
  }
  return undefined;
}

export const useChatStore = create<ChatState>((set, get) => {
  async function turn(
    body: Parameters<typeof postChatTurn>[0],
    userText: string | null,
  ): Promise<void> {
    if (get().pending) return;
    const base = userText
      ? [...get().entries, { id: nextId(), role: "user" as const, text: userText }]
      : get().entries;
    set({ pending: true, entries: base });
    try {
      const res = await postChatTurn({ ...body, sessionId: get().sessionId });
      set({
        sessionId: res.sessionId,
        phase: res.phase,
        poolTotal: res.poolTotal,
        candidateCount: res.candidateCount,
        pending: false,
        entries: [
          ...get().entries,
          {
            id: nextId(),
            role: "bot",
            text: res.botText,
            cards: res.cards.length > 0 ? res.cards : undefined,
            board: boardOf(res),
          },
        ],
      });
    } catch {
      set({
        pending: false,
        entries: [...get().entries, { id: nextId(), role: "bot", text: ERROR_TEXT }],
      });
    }
  }

  return {
    sessionId: null,
    phase: "refining",
    poolTotal: null,
    candidateCount: null,
    entries: [],
    pending: false,

    send: (utterance: string) => {
      const t = utterance.trim();
      if (!t) return Promise.resolve();
      return turn({ utterance: t }, t);
    },

    pickAnswer: (answer: ChatAnswer) => {
      switch (answer.kind) {
        case "ask":
          return turn({ utterance: answer.utterance ?? answer.label }, answer.label);
        case "skip":
          return turn({ skip: true }, answer.label);
        case "remove":
          return turn({ removeConditionId: answer.removeConditionId ?? undefined }, answer.label);
        case "commit":
          get().commit();
          return Promise.resolve();
        case "restart":
          get().reset();
          return Promise.resolve();
        default:
          return Promise.resolve();
      }
    },

    removeCondition: (id: string) => turn({ removeConditionId: id }, null),

    commit: () => {
      const entry = latestBoardEntry(get().entries);
      const board = entry?.board;
      const spots = entry?.cards ?? [];
      const region = board?.conditions.find((c) => c.id.startsWith("region:"));
      const title = region ? `${region.label}에서 찾은 곳` : "오늘 찾은 곳";
      const summary = (board?.conditions ?? []).map((c) => c.label).join(" · ");
      set({
        phase: "done",
        entries: [
          ...get().entries,
          {
            id: nextId(),
            role: "conclusion",
            text: title,
            conclusion: { title, spots, summary },
          },
        ],
      });
    },

    reset: () => {
      set({
        sessionId: null,
        phase: "refining",
        poolTotal: null,
        candidateCount: null,
        entries: [],
        pending: false,
      });
    },
  };
});
