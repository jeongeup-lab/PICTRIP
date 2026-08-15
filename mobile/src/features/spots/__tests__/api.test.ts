import { api } from "@/lib/api-client";
import { getNearby, getSpot } from "@/features/spots/api";

jest.mock("@/lib/api-client", () => ({ api: { get: jest.fn() } }));

describe("spots api", () => {
  beforeEach(() => jest.clearAllMocks());

  it("opts into deferred detail responses", async () => {
    (api.get as jest.Mock).mockResolvedValue({});

    await getSpot("123");

    expect(api.get).toHaveBeenCalledWith("/spots/123", {
      headers: { "X-PicTrip-Detail-Mode": "deferred-v1" },
    });
  });

  it("requests nearby spots with the detail page radius", async () => {
    (api.get as jest.Mock).mockResolvedValue([]);

    await getNearby(37.5, 127);

    expect(api.get).toHaveBeenCalledWith("/map/nearby", {
      params: { lat: 37.5, lng: 127, radius: 3000 },
    });
  });
});
