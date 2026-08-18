import { getChannelCards, getChannels } from "@/features/channels/api";
import { api } from "@/lib/api-client";

jest.mock("@/lib/api-client", () => ({ api: { get: jest.fn() } }));

describe("channels api", () => {
  beforeEach(() => jest.clearAllMocks());

  it("getChannels hits /home/channels", async () => {
    (api.get as jest.Mock).mockResolvedValue({ channels: [] });
    await getChannels();
    expect(api.get).toHaveBeenCalledWith("/home/channels", { params: {} });
  });

  it("getChannels forwards coords", async () => {
    (api.get as jest.Mock).mockResolvedValue({ channels: [] });
    await getChannels({ lat: 35.1, lng: 129.0 });
    expect(api.get).toHaveBeenCalledWith("/home/channels", {
      params: { lat: 35.1, lng: 129.0 },
    });
  });

  it("getChannelCards hits the channel path", async () => {
    (api.get as jest.Mock).mockResolvedValue({ key: "hidden", label: "Hidden", cards: [] });
    await getChannelCards("hidden", { lat: 35.1, lng: 129.0 });
    expect(api.get).toHaveBeenCalledWith("/home/channels/hidden", {
      params: { lat: 35.1, lng: 129.0 },
    });
  });
});
