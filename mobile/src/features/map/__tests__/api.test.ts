import { api } from "@/lib/api-client";
import { getNearby, getRegionLabel, getRegionsTree } from "@/features/map/api";

jest.mock("@/lib/api-client", () => ({ api: { get: jest.fn() } }));

describe("map api", () => {
  beforeEach(() => jest.clearAllMocks());

  it("getNearby sends lat/lng/radius and category when given", async () => {
    (api.get as jest.Mock).mockResolvedValue([]);
    await getNearby(37.5, 127, "cafe");
    expect(api.get).toHaveBeenCalledWith("/map/nearby", {
      params: { lat: 37.5, lng: 127, radius: 3000, category: "cafe" },
    });
  });

  it("getNearby omits category when null", async () => {
    (api.get as jest.Mock).mockResolvedValue([]);
    await getNearby(37.5, 127, null);
    expect(api.get).toHaveBeenCalledWith("/map/nearby", {
      params: { lat: 37.5, lng: 127, radius: 3000, category: undefined },
    });
  });

  it("getRegionLabel sends lat/lng", async () => {
    (api.get as jest.Mock).mockResolvedValue({ label: "서울 중구" });
    const r = await getRegionLabel(37.5, 127);
    expect(api.get).toHaveBeenCalledWith("/map/region", { params: { lat: 37.5, lng: 127 } });
    expect(r.label).toBe("서울 중구");
  });

  it("getRegionsTree calls the tree endpoint", async () => {
    (api.get as jest.Mock).mockResolvedValue([]);
    await getRegionsTree();
    expect(api.get).toHaveBeenCalledWith("/map/regions-tree");
  });
});
