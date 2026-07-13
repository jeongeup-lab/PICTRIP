import { getPosts, getMatches } from "@/features/feed/posts-api";
import { api } from "@/lib/api-client";

jest.mock("@/lib/api-client", () => ({ api: { get: jest.fn() } }));

describe("posts api", () => {
  beforeEach(() => jest.clearAllMocks());

  it("getPosts hits /feed with seed/cursor/limit params", async () => {
    (api.get as jest.Mock).mockResolvedValue({
      seed: "s1",
      items: [],
      nextCursor: null,
      hasMore: false,
    });
    await getPosts({ seed: "s1", cursor: "c1", limit: 6 });
    expect(api.get).toHaveBeenCalledWith("/feed", {
      params: { seed: "s1", cursor: "c1", limit: 6 },
    });
  });

  it("getPosts omits absent params", async () => {
    (api.get as jest.Mock).mockResolvedValue({
      seed: "s",
      items: [],
      nextCursor: null,
      hasMore: false,
    });
    await getPosts({});
    expect(api.get).toHaveBeenCalledWith("/feed", { params: {} });
  });

  it("getMatches hits /overseas/{id}/matches", async () => {
    (api.get as jest.Mock).mockResolvedValue({ overseasId: 42, matches: [] });
    await getMatches(42);
    expect(api.get).toHaveBeenCalledWith("/overseas/42/matches");
  });
});
