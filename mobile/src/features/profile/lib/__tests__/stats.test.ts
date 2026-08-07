import { daysSince, profileStats } from "@/features/profile/lib/stats";
import type { SpotCard } from "@/lib/api-types";

const spot = (contentId: string, addr1: string | null): SpotCard => ({
  contentId,
  title: `spot-${contentId}`,
  firstImageUrl: null,
  addr1,
  mapx: null,
  mapy: null,
  category: null,
});

const NOW = Date.parse("2026-08-08T00:00:00Z");

describe("profileStats", () => {
  it("is all zeros before anything is saved", () => {
    expect(profileStats(undefined, null, NOW)).toEqual({ saved: 0, regions: 0, days: 0 });
  });

  it("counts saved spots and the distinct regions they sit in", () => {
    const stats = profileStats(
      [spot("1", "경남 통영시"), spot("2", "경남 고성군"), spot("3", "전남 여수시")],
      "2026-08-01T00:00:00Z",
      NOW,
    );
    expect(stats).toEqual({ saved: 3, regions: 2, days: 8 });
  });
});

describe("daysSince", () => {
  it("counts the join day itself, so a fresh account reads 1", () => {
    expect(daysSince("2026-08-08T09:00:00Z", NOW)).toBe(1);
  });

  it("falls back to zero when the server sent no join date", () => {
    expect(daysSince(null, NOW)).toBe(0);
    expect(daysSince("not-a-date", NOW)).toBe(0);
  });
});
