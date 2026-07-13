import { warmConnection } from "@/lib/warm-connection";

describe("warmConnection", () => {
  const originalFetch = global.fetch;
  afterEach(() => {
    global.fetch = originalFetch;
    jest.clearAllMocks();
  });

  it("pings root /health (base with /v1 stripped) to warm the connection", () => {
    const fetchMock = jest.fn().mockResolvedValue({ ok: true });
    global.fetch = fetchMock as unknown as typeof fetch;
    warmConnection();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("https://api.pictrip.org/health");
    expect(fetchMock.mock.calls[0][1]).toEqual({ method: "GET" });
  });

  it("swallows network errors so a cold/offline start never throws", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("offline")) as unknown as typeof fetch;
    expect(() => warmConnection()).not.toThrow();
    await Promise.resolve();
  });
});
