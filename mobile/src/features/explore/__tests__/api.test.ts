import { getExplore } from "@/features/explore/api";
import { api } from "@/lib/api-client";

jest.mock("@/lib/api-client", () => ({ api: { get: jest.fn() } }));

describe("explore api", () => {
  beforeEach(() => jest.clearAllMocks());

  it("getExplore hits /explore with seed/cursor/limit params", async () => {
    (api.get as jest.Mock).mockResolvedValue({
      seed: "s1",
      items: [],
      nextCursor: null,
      hasMore: false,
    });
    await getExplore({ seed: "s1", cursor: "c1", limit: 30 });
    expect(api.get).toHaveBeenCalledWith("/explore", {
      params: { seed: "s1", cursor: "c1", limit: 30 },
    });
  });

  it("getExplore omits absent params", async () => {
    (api.get as jest.Mock).mockResolvedValue({
      seed: "s",
      items: [],
      nextCursor: null,
      hasMore: false,
    });
    await getExplore({});
    expect(api.get).toHaveBeenCalledWith("/explore", { params: {} });
  });
});
