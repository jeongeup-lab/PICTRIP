import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useChannelCards } from "@/features/channels/queries";
import { getChannelCards } from "@/features/channels/api";

jest.mock("@/features/channels/api", () => ({ getChannelCards: jest.fn() }));

function Probe({ coords }: { coords: { lat: number; lng: number } }) {
  const { data } = useChannelCards("around", coords);
  return <Text>{data ? "ok" : "loading"}</Text>;
}

function wrap(client: QueryClient, coords: { lat: number; lng: number }) {
  return (
    <QueryClientProvider client={client}>
      <Probe coords={coords} />
    </QueryClientProvider>
  );
}

describe("useChannelCards coords cache key", () => {
  beforeEach(() => jest.clearAllMocks());

  it("re-fetches around cards when the location changes", async () => {
    (getChannelCards as jest.Mock).mockResolvedValue({ key: "around", label: "A", cards: [] });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    let tree: renderer.ReactTestRenderer;
    await act(async () => {
      tree = renderer.create(wrap(client, { lat: 37.5, lng: 127.0 }));
    });
    await act(async () => {
      tree!.update(wrap(client, { lat: 35.1, lng: 129.0 }));
    });
    const coordArgs = (getChannelCards as jest.Mock).mock.calls.map((c) => c[1]);
    expect(coordArgs).toEqual(
      expect.arrayContaining([
        { lat: 37.5, lng: 127.0 },
        { lat: 35.1, lng: 129.0 },
      ]),
    );
    client.clear();
  });

  it("reuses the cache for sub-100m GPS jitter", async () => {
    (getChannelCards as jest.Mock).mockResolvedValue({ key: "around", label: "A", cards: [] });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    let tree: renderer.ReactTestRenderer;
    await act(async () => {
      tree = renderer.create(wrap(client, { lat: 37.5, lng: 127.0 }));
    });
    await act(async () => {
      tree!.update(wrap(client, { lat: 37.5001, lng: 127.0001 }));
    });
    expect((getChannelCards as jest.Mock).mock.calls).toHaveLength(1);
    client.clear();
  });
});
