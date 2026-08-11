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

  it("getChannelCards hits the channel path", async () => {
    (api.get as jest.Mock).mockResolvedValue({ key: "hidden", label: "Hidden", cards: [] });
    await getChannelCards("hidden");
    expect(api.get).toHaveBeenCalledWith("/home/channels/hidden");
  });
});
