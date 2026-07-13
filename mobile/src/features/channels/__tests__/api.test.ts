import { getChannelCards, getChannels } from "@/features/channels/api";
import { api } from "@/lib/api-client";

jest.mock("@/lib/api-client", () => ({ api: { get: jest.fn() } }));

describe("channels api", () => {
  beforeEach(() => jest.clearAllMocks());

  it("getChannels hits /home/channels", async () => {
    (api.get as jest.Mock).mockResolvedValue({ channels: [] });
    await getChannels();
    expect(api.get).toHaveBeenCalledWith("/home/channels");
  });

  it("getChannelCards passes coords for around", async () => {
    (api.get as jest.Mock).mockResolvedValue({ key: "around", label: "Around", cards: [] });
    await getChannelCards("around", { lat: 35.1, lng: 129 });
    expect(api.get).toHaveBeenCalledWith("/home/channels/around", {
      params: { lat: 35.1, lng: 129 },
    });
  });

  it("getChannelCards omits coords for keyless channels", async () => {
    (api.get as jest.Mock).mockResolvedValue({ key: "hot", label: "Hot", cards: [] });
    await getChannelCards("hot");
    expect(api.get).toHaveBeenCalledWith("/home/channels/hot", { params: undefined });
  });
});
