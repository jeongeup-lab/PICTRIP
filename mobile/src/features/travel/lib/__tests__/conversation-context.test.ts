import { contextFrom, MAX_CONTEXT_SPOTS } from "@/features/travel/lib/conversation-context";
import type { AgentAnswer, TravelSpot } from "@/features/travel/api";

const spot = (id: string): TravelSpot => ({
  contentId: id,
  title: `spot-${id}`,
  regionLabel: "제주 제주시",
  imageUrl: null,
  tag: null,
  lat: null,
  lng: null,
});

const answer = (over: Partial<AgentAnswer> = {}): AgentAnswer => ({
  steps: [],
  answer: [],
  spots: [spot("a"), spot("b")],
  totalCount: 2,
  intent: { categoryKeywords: ["해수욕장"], regionHints: ["제주"] },
  suggestions: [],
  refinements: [],
  ...over,
});

describe("contextFrom", () => {
  it("is null when there is no previous answer", () => {
    expect(contextFrom(null)).toBeNull();
    expect(contextFrom(undefined)).toBeNull();
  });

  it("carries the applied intent and the result titles", () => {
    const context = contextFrom(answer());

    expect(context?.intent?.categoryKeywords).toEqual(["해수욕장"]);
    expect(context?.spots).toEqual([
      { contentId: "a", title: "spot-a" },
      { contentId: "b", title: "spot-b" },
    ]);
  });

  it("sends only the id and title, never the whole card", () => {
    const context = contextFrom(answer());

    expect(Object.keys(context!.spots[0]).sort()).toEqual(["contentId", "title"]);
  });

  it("caps the carried results so the prompt stays bounded", () => {
    const many = Array.from({ length: 20 }, (_, i) => spot(`s${i}`));

    expect(contextFrom(answer({ spots: many }))?.spots).toHaveLength(MAX_CONTEXT_SPOTS);
  });

  it("still carries an intent when the answer found nothing", () => {
    const context = contextFrom(answer({ spots: [] }));

    expect(context?.spots).toEqual([]);
    expect(context?.intent).not.toBeNull();
  });
});
