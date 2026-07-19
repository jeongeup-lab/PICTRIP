export interface ChatCondition {
  id: string;
  label: string;
  exclude: boolean;
}

export interface ChatCard {
  contentId: string;
  title: string;
  firstImageUrl: string;
  category: string | null;
  regionLabel: string;
  why: string;
  quiet: boolean | null;
}

export type ChatAnswerKind = "ask" | "skip" | "remove" | "commit" | "restart";

export interface ChatAnswer {
  id: string;
  label: string;
  kind: ChatAnswerKind;
  utterance?: string | null;
  removeConditionId?: string | null;
}

export type ChatPhase = "refining" | "converged" | "empty";

export interface ChatTurnResponse {
  sessionId: string;
  round: number;
  phase: ChatPhase;
  poolTotal: number;
  candidateCount: number;
  conditions: ChatCondition[];
  botText: string;
  cards: ChatCard[];
  question: string;
  answers: ChatAnswer[];
}

export interface ChatTurnBody {
  sessionId?: string | null;
  utterance?: string;
  removeConditionId?: string;
  skip?: boolean;
}

/** One 스무고개 round the board can render (full when latest, compact when history). */
export interface ChatBoard {
  round: number;
  phase: ChatPhase;
  poolTotal: number;
  candidateCount: number;
  conditions: ChatCondition[];
  question: string;
  answers: ChatAnswer[];
}

export type ChatEntryRole = "user" | "bot" | "conclusion";

export interface ChatEntry {
  id: string;
  role: ChatEntryRole;
  text: string;
  cards?: ChatCard[];
  board?: ChatBoard;
  /** conclusion entries carry the locked spots + condition summary. */
  conclusion?: { title: string; spots: ChatCard[]; summary: string };
}
