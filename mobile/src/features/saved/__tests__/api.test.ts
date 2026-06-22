import { api } from "@/lib/api-client";
import { listSaved, saveSpot, unsaveSpot } from "@/features/saved/api";

jest.mock("@/lib/api-client", () => ({
  api: { get: jest.fn(), post: jest.fn(), delete: jest.fn() },
}));

describe("saved api", () => {
  beforeEach(() => jest.clearAllMocks());

  it("listSaved gets the saved list with limit 60", async () => {
    const cards = [{ contentId: "1", title: "a", firstImageUrl: null, category: null }];
    (api.get as jest.Mock).mockResolvedValue(cards);
    const res = await listSaved();
    expect(api.get).toHaveBeenCalledWith("/users/me/saved", { params: { limit: 60 } });
    expect(res).toBe(cards);
  });

  it("saveSpot posts to the content path", async () => {
    (api.post as jest.Mock).mockResolvedValue({});
    await saveSpot("123");
    expect(api.post).toHaveBeenCalledWith("/users/me/saved/123");
  });

  it("unsaveSpot deletes the content path", async () => {
    (api.delete as jest.Mock).mockResolvedValue(undefined);
    await unsaveSpot("123");
    expect(api.delete).toHaveBeenCalledWith("/users/me/saved/123");
  });
});
