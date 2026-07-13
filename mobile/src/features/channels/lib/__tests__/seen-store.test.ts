import { loadSeen, saveSeen } from "@/features/channels/lib/seen-store";

jest.mock("@/lib/storage", () => {
  let value: string | null = null;
  return {
    getSeenChannelsRaw: jest.fn(async () => value),
    setSeenChannelsRaw: jest.fn(async (v: string) => {
      value = v;
    }),
  };
});

describe("seen-store", () => {
  it("round-trips today's seen keys", async () => {
    await saveSeen(["hot"], "2026-07-12");
    expect(await loadSeen("2026-07-12")).toEqual(["hot"]);
  });

  it("resets when the stored day differs", async () => {
    await saveSeen(["hot"], "2026-07-12");
    expect(await loadSeen("2026-07-13")).toEqual([]);
  });
});
