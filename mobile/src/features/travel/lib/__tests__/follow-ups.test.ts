import {
  ABOUT_LABEL,
  askedKeys,
  DETAIL_LINE,
  followUps,
  MAX_FOLLOW_CHIPS,
  NEAR_FOOD_LABEL,
  RELATED_LABEL,
  SEARCH_LINE,
} from "@/features/travel/lib/follow-ups";
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

const REFINEMENTS = [
  { label: "사람 적은 곳만", patch: { crowdPreference: "quiet" as const } },
  { label: "실내만", patch: { indoorOnly: true } },
  { label: "다른 지역도 보기", patch: { drop: "region" as const } },
];

describe("검색 턴은 결과를 다루는 칩만 낸다", () => {
  it("서버 refine 뒤에 '이 곳 더 알아보기' 입구 하나", () => {
    const block = followUps({ ...base, refinements: REFINEMENTS.slice(0, 2) });

    expect(block.line).toBe(SEARCH_LINE);
    expect(block.chips.map((c) => c.label)).toEqual(["사람 적은 곳만", "실내만", ABOUT_LABEL]);
  });

  it("연관 관광지·근처 맛집은 검색 턴에 나오지 않는다", () => {
    const labels = followUps(base).chips.map((c) => c.label);

    expect(labels).not.toContain(RELATED_LABEL);
    expect(labels).not.toContain(NEAR_FOOD_LABEL);
  });

  it("about 칩은 스팟이 특정될 때만 뜬다", () => {
    const block = followUps({ ...base, contentId: null });

    expect(block.chips.map((c) => c.label)).not.toContain(ABOUT_LABEL);
  });

  it("이미 물어본 about 은 다시 권하지 않는다", () => {
    const block = followUps({ ...base, asked: new Set(["detail:about:c1"]) });

    expect(block.chips.map((c) => c.label)).not.toContain(ABOUT_LABEL);
  });
});

describe("상세 턴은 그 곳에서 뻗는 칩만 낸다", () => {
  it("연관 관광지 · 근처 맛집", () => {
    const block = followUps({ ...base, isDetailTurn: true });

    expect(block.line).toBe(DETAIL_LINE);
    expect(block.chips.map((c) => c.label)).toEqual([RELATED_LABEL, NEAR_FOOD_LABEL]);
  });

  it("about 을 되묻지 않는다", () => {
    const block = followUps({ ...base, isDetailTurn: true });

    expect(block.chips.map((c) => c.label)).not.toContain(ABOUT_LABEL);
  });

  it("이미 물어본 앵커는 빠진다", () => {
    const block = followUps({
      ...base,
      isDetailTurn: true,
      asked: new Set(["anchor:related:c1"]),
    });

    expect(block.chips.map((c) => c.label)).toEqual([NEAR_FOOD_LABEL]);
  });

  it("연관 관광지 칩은 임베딩 앵커를 부른다", () => {
    const block = followUps({ ...base, isDetailTurn: true });

    expect(block.chips[0].action).toEqual({
      kind: "anchor",
      action: "related",
      question: "동피랑 벽화마을 연관 관광지는?",
    });
  });
});

describe("칩 수 상한", () => {
  it("어떤 조합이든 3개를 넘지 않는다", () => {
    const block = followUps({
      ...base,
      refinements: REFINEMENTS,
      suggestions: ["근처 카페 알려줘", "주차 되는 곳"],
    });

    expect(block.chips).toHaveLength(MAX_FOLLOW_CHIPS);
  });

  it("자리가 남으면 서버 제안 질문이 채운다", () => {
    const block = followUps({ ...base, contentId: null, suggestions: ["통영 야경 어디가 좋아?"] });

    expect(block.chips.map((c) => c.label)).toEqual(["통영 야경 어디가 좋아?"]);
    expect(block.chips[0].action).toEqual({
      kind: "question",
      question: "통영 야경 어디가 좋아?",
    });
  });

  it("이미 물어본 제안 질문은 빠진다", () => {
    const block = followUps({
      ...base,
      contentId: null,
      suggestions: ["통영 야경 어디가 좋아?"],
      asked: new Set(["q:통영 야경 어디가 좋아?"]),
    });

    expect(block.chips).toEqual([]);
  });
});

describe("askedKeys", () => {
  it("앵커·상세·자유질문을 각각의 키로 기억한다", () => {
    const keys = askedKeys([
      { ...turnBase, anchor: { contentId: "c1", action: "related" } },
      { ...turnBase, followKey: "about", context: { focusContentId: "c1" } },
      { ...turnBase, request: "통영 야경" },
    ] as Turn[]);

    expect(keys.has("anchor:related:c1")).toBe(true);
    expect(keys.has("detail:about:c1")).toBe(true);
    expect(keys.has("q:통영 야경")).toBe(true);
  });
});
