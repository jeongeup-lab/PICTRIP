import { api } from "@/lib/api-client";
import { getNearby, getRegionLabel, getRegionsTree } from "@/features/map/api";

jest.mock("@/lib/api-client", () => ({ api: { get: jest.fn() } }));

describe("map api", () => {
  beforeEach(() => jest.clearAllMocks());

  const bbox = { sw: { lat: 37.4, lng: 126.9 }, ne: { lat: 37.6, lng: 127.1 } };

  it("getNearby sends the bbox corners and category when given", async () => {
    (api.get as jest.Mock).mockResolvedValue([]);
    await getNearby(bbox, "cafe");
    expect(api.get).toHaveBeenCalledWith("/map/nearby", {
      params: { sw_lat: 37.4, sw_lng: 126.9, ne_lat: 37.6, ne_lng: 127.1, category: "cafe" },
    });
  });

  it("getNearby omits category when null", async () => {
    (api.get as jest.Mock).mockResolvedValue([]);
    await getNearby(bbox, null);
    expect(api.get).toHaveBeenCalledWith("/map/nearby", {
      params: { sw_lat: 37.4, sw_lng: 126.9, ne_lat: 37.6, ne_lng: 127.1, category: undefined },
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
