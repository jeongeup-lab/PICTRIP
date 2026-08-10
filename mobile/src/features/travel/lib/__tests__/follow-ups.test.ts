import { askedKeys, followUps } from "@/features/travel/lib/follow-ups";
import type { Turn } from "@/features/travel/stores/conversation-store";

const CAFE_CATEGORY_GROUP = "cafe";

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
  categoryGroup: null,
  hasCrowd: false,
  branch: "root" as const,
  asked: new Set<string>(),
  isDetailTurn: false,
  refinements: null,
  suggestions: null,
};

describe("followUps 루트", () => {
  it("안내 문장 + 근처/정보 칩", () => {
    const b = followUps(base);
    expect(b.line).toBe(
      "동피랑 벽화마을 근처의 카페·맛집·볼거리를 찾아드릴 수도 있고, 어떤 곳인지 더 알려드릴 수도 있어요.",
    );
    expect(b.chips.map((c) => c.label)).toEqual(["근처 뭐 있어?", "여긴 어떤 곳이야?"]);
    expect(b.chips[1].action).toEqual({
      kind: "detail",
      followKey: "about",
      question: "동피랑 벽화마을은 어떤 곳이야?",
    });
  });

  it("about을 이미 물었으면 다음 정보 칩(영업시간)으로 순환", () => {
    const b = followUps({ ...base, asked: new Set(["detail:about:c1"]) });
    expect(b.chips.map((c) => c.label)).toEqual(["근처 뭐 있어?", "영업시간은?"]);
  });

  it("refinements가 맨 앞에 서고 suggestions는 뒤에 붙어 5개로 캡", () => {
    const b = followUps({
      ...base,
      refinements: [
        { label: "조용한 곳만", patch: { crowdPreference: "quiet" } },
        { label: "실내만", patch: { indoorOnly: true } },
      ],
      suggestions: ["야경 좋은 곳도 볼래?", "비 오는 날 코스는?"],
    });
    expect(b.chips.map((c) => c.label)).toEqual([
      "조용한 곳만",
      "실내만",
      "근처 뭐 있어?",
      "여긴 어떤 곳이야?",
      "야경 좋은 곳도 볼래?",
    ]);
    expect(b.chips[0].action).toEqual({
      kind: "refine",
      label: "조용한 곳만",
      patch: { crowdPreference: "quiet" },
    });
    expect(b.chips[4].action).toEqual({ kind: "question", question: "야경 좋은 곳도 볼래?" });
  });

  it("refinement와 같은 라벨의 suggestion은 다시 붙이지 않는다", () => {
    const b = followUps({
      ...base,
      refinements: [{ label: "실내만", patch: { indoorOnly: true } }],
      suggestions: ["실내만"],
    });
    expect(b.chips.filter((c) => c.label === "실내만")).toHaveLength(1);
  });

  it("이미 물은 suggestion은 제외", () => {
    const b = followUps({
      ...base,
      suggestions: ["야경 좋은 곳도 볼래?"],
      asked: new Set(["q:야경 좋은 곳도 볼래?"]),
    });
    expect(b.chips.map((c) => c.label)).not.toContain("야경 좋은 곳도 볼래?");
  });
});

describe("followUps near 분기 — 중복 방지", () => {
  it("기본: 카페/맛집/볼거리 + 뒤로", () => {
    const b = followUps({ ...base, branch: "near" });
    expect(b.line).toBe("어떤 곳부터 찾아볼까요?");
    expect(b.chips.map((c) => c.label)).toEqual(["카페", "맛집", "볼거리", "‹ 뒤로"]);
    expect(b.chips[0].action).toEqual({
      kind: "anchor",
      action: "cafe",
      question: "동피랑 벽화마을 근처 카페",
    });
  });

  it("이미 물은 앵커(카페)는 빠진다", () => {
    const b = followUps({ ...base, branch: "near", asked: new Set(["anchor:cafe:c1"]) });
    expect(b.chips.map((c) => c.label)).toEqual(["맛집", "볼거리", "‹ 뒤로"]);
  });

  it("포커스 스팟이 카페면 근처 카페를 제안하지 않는다", () => {
    const b = followUps({ ...base, branch: "near", categoryGroup: CAFE_CATEGORY_GROUP });
    expect(b.chips.map((c) => c.label)).not.toContain("카페");
  });

  it("hasCrowd면 지금 붐벼? 칩이 붙는다 (crowd anchor)", () => {
    const b = followUps({ ...base, branch: "near", hasCrowd: true });
    expect(b.chips.map((c) => c.label)).toContain("지금 붐벼?");
  });

  it("전부 물었으면 루트에서 근처 뭐 있어?가 사라진다", () => {
    const b = followUps({
      ...base,
      asked: new Set(["anchor:cafe:c1", "anchor:food:c1", "anchor:nearby:c1"]),
    });
    expect(b.chips.map((c) => c.label)).not.toContain("근처 뭐 있어?");
  });
});

describe("포커스 스팟이 없을 때", () => {
  const noFocus = { ...base, title: "내 위치", contentId: null };

  it("정보 칩 없이 근처 안내 문장만 남는다", () => {
    const b = followUps(noFocus);
    expect(b.line).toBe("내 위치 근처의 카페·맛집·볼거리를 찾아드릴 수 있어요.");
    expect(b.chips.map((c) => c.label)).toEqual(["근처 뭐 있어?"]);
  });

  it("isDetailTurn이어도 정보 칩이 생기지 않는다", () => {
    const b = followUps({ ...noFocus, isDetailTurn: true });
    expect(b.line).toBe("내 위치 근처의 카페·맛집·볼거리를 찾아드릴 수 있어요.");
    expect(b.chips.map((c) => c.label)).toEqual(["근처 뭐 있어?"]);
  });

  it("refinements가 앞, suggestions가 뒤에 붙는다", () => {
    const b = followUps({
      ...noFocus,
      refinements: [{ label: "실내만", patch: { indoorOnly: true } }],
      suggestions: ["야경 좋은 곳도 볼래?"],
    });
    expect(b.chips.map((c) => c.label)).toEqual([
      "실내만",
      "근처 뭐 있어?",
      "야경 좋은 곳도 볼래?",
    ]);
  });
});

describe("정보 답변 뒤", () => {
  it("남은 정보 칩 + 근처 칩, 물은 건 제외", () => {
    const b = followUps({
      ...base,
      isDetailTurn: true,
      asked: new Set(["detail:about:c1", "detail:hours:c1"]),
    });
    expect(b.line).toBe("더 궁금한 게 있으세요?");
    expect(b.chips.map((c) => c.label)).toEqual([
      "연관 관광지는?",
      "주차는 돼?",
      "이용요금은?",
      "근처 뭐 있어?",
    ]);
    expect(b.chips[0].action).toEqual({
      kind: "anchor",
      action: "related",
      question: "동피랑 벽화마을 연관 관광지는?",
    });
  });
});

describe("askedKeys", () => {
  it("앵커·detail·질문 턴에서 키를 뽑는다", () => {
    const keys = askedKeys([
      { ...turnBase, anchor: { contentId: "c1", action: "cafe" } },
      { ...turnBase, followKey: "hours", context: { spots: [], focusContentId: "c1" } },
      { ...turnBase, request: "야경 좋은 곳도 볼래?" },
    ] as Turn[]);
    expect(keys.has("anchor:cafe:c1")).toBe(true);
    expect(keys.has("detail:hours:c1")).toBe(true);
    expect(keys.has("q:야경 좋은 곳도 볼래?")).toBe(true);
  });
});
