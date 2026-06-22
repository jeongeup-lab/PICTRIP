import { api } from "@/lib/api-client";
import { photoSearch } from "@/features/photo/api";

jest.mock("@/lib/api-client", () => ({ api: { post: jest.fn() } }));

const asset = { uri: "file:///x.jpg", mimeType: "image/jpeg", fileName: "x.jpg" };

describe("photoSearch", () => {
  beforeEach(() => jest.clearAllMocks());

  it("posts multipart FormData with lat/lng params when coords given", async () => {
    (api.post as jest.Mock).mockResolvedValue({ matches: [], queryHadLocation: true });
    const res = await photoSearch(asset, { lat: 1, lng: 2 });
    expect(api.post).toHaveBeenCalledWith(
      "/taste/photo-search",
      expect.any(FormData),
      expect.objectContaining({ params: { lat: 1, lng: 2 } }),
    );
    expect(res.queryHadLocation).toBe(true);
  });

  it("omits params when coords is null and forwards the abort signal", async () => {
    (api.post as jest.Mock).mockResolvedValue({ matches: [], queryHadLocation: false });
    const controller = new AbortController();
    await photoSearch(asset, null, controller.signal);
    expect(api.post).toHaveBeenCalledWith(
      "/taste/photo-search",
      expect.any(FormData),
      expect.objectContaining({ params: undefined, signal: controller.signal }),
    );
  });

  it("returns the unwrapped result without re-unwrapping", async () => {
    const payload = { matches: [{ contentId: "1" }], queryHadLocation: false };
    (api.post as jest.Mock).mockResolvedValue(payload);
    expect(await photoSearch(asset, null)).toBe(payload);
  });
});
