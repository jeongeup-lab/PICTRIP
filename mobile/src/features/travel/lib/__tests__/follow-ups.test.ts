import {
  askedKeys,
  FOLLOW_LINE,
  followUps,
  MAX_FOLLOW_CHIPS,
} from "@/features/travel/lib/follow-ups";
import { NEAR_CHIPS } from "@/features/travel/lib/starter-chips";
import type { Turn } from "@/features/travel/stores/conversation-store";

const turnBase: Turn = {
  id: "t1",
  question: "",
  request: "",
  photo: null,
  intent: null,
  patch: null,
  anchor: null,
  context: null,
  status: "done",
  answer: null,
  errorMessage: null,
};

const base = {
  title: "동피랑 벽화마을",
  contentId: "c1",
  asked: new Set<string>(),
  isDetailTurn: false,
  refinements: null,
  suggestions: null,
};

const NEAR_LABELS = NEAR_CHIPS.map((chip) => chip.label);

const REFINEMENTS = [
  { label: "사람 적은 곳만", patch: { crowdPreference: "quiet" as const } },
  { label: "실내만", patch: { indoorOnly: true } },
  { label: "다른 지역도 보기", patch: { drop: "region" as const } },
];

describe("후속 칩은 근처 세 갈래로 고정된다", () => {
  it("서버가 아무것도 안 줘도 세 개가 선다", () => {
    const block = followUps(base);

    expect(block.line).toBe(FOLLOW_LINE);
    expect(block.chips.map((c) => c.label)).toEqual(NEAR_LABELS);
  });

  it("포커스한 스팟을 앵커로 물고 나간다", () => {
    const block = followUps(base);

    expect(block.chips[0].action).toEqual({
      kind: "anchor",
      action: "cafe",
      question: "동피랑 벽화마을 근처 카페",
    });
  });

  it("이미 물어본 앵커는 빠진다", () => {
    const block = followUps({ ...base, asked: new Set(["anchor:cafe:c1"]) });

    expect(block.chips.map((c) => c.label)).toEqual(["근처 맛집", "근처 볼거리"]);
  });

  it("포커스한 스팟이 없으면 내 위치 기준으로 나간다", () => {
    const block = followUps({ ...base, title: "내 위치", contentId: null });

    expect(block.chips[0].action).toEqual({
      kind: "anchor",
      action: "cafe",
      question: "내 위치 근처 카페",
    });
  });
});

describe("서버 refinement 는 근처 칩 뒤에 붙는다", () => {
  it("최대 두 개까지만 붙는다", () => {
    const block = followUps({ ...base, refinements: REFINEMENTS });

    expect(block.chips.map((c) => c.label)).toEqual([...NEAR_LABELS, "사람 적은 곳만", "실내만"]);
    expect(block.chips).toHaveLength(MAX_FOLLOW_CHIPS);
  });

  it("refine 칩은 patch 를 그대로 실어 보낸다", () => {
    const block = followUps({ ...base, refinements: [REFINEMENTS[1]] });

    expect(block.chips[3].action).toEqual({
      kind: "refine",
      label: "실내만",
      patch: { indoorOnly: true },
    });
  });

  it("근처 칩이 빠진 자리를 refinement 가 대신 채우지는 않는다", () => {
    const block = followUps({
      ...base,
      asked: new Set(["anchor:cafe:c1", "anchor:food:c1", "anchor:nearby:c1"]),
      refinements: REFINEMENTS,
    });

    expect(block.chips.map((c) => c.label)).toEqual(["사람 적은 곳만", "실내만"]);
  });
});

describe("askedKeys", () => {
  it("앵커·상세·자유질문을 각각의 키로 기억한다", () => {
    const keys = askedKeys([
      { ...turnBase, anchor: { contentId: "c1", action: "cafe" } },
      { ...turnBase, followKey: "about", context: { focusContentId: "c1" } },
      { ...turnBase, request: "통영 야경" },
    ] as Turn[]);

    expect(keys.has("anchor:cafe:c1")).toBe(true);
    expect(keys.has("detail:about:c1")).toBe(true);
    expect(keys.has("q:통영 야경")).toBe(true);
  });
});
