import { buildSavedCsv } from "@/features/saved/lib/export-csv";
import type { SpotCard } from "@/lib/api-types";

const spot = (over: Partial<SpotCard> & { contentId: string }): SpotCard => ({
  title: `spot-${over.contentId}`,
  firstImageUrl: null,
  addr1: null,
  mapx: null,
  mapy: null,
  category: null,
  ...over,
});

describe("buildSavedCsv", () => {
  it("writes only the header for an empty list", () => {
    expect(buildSavedCsv([])).toBe("contentId,title,address,category,lat,lng");
  });

  it("writes one line per spot with blanks for missing fields", () => {
    const csv = buildSavedCsv([
      spot({
        contentId: "126508",
        title: "소매물도",
        addr1: "경남 통영시",
        mapx: 128.5,
        mapy: 34.6,
      }),
      spot({ contentId: "1", title: "이름만" }),
    ]);
    expect(csv.split("\n")).toEqual([
      "contentId,title,address,category,lat,lng",
      "126508,소매물도,경남 통영시,,34.6,128.5",
      "1,이름만,,,,",
    ]);
  });

  it("quotes values holding commas or quotes", () => {
    const csv = buildSavedCsv([spot({ contentId: "1", title: 'a,b "c"' })]);
    expect(csv.split("\n")[1]).toBe('1,"a,b ""c""",,,,');
  });
});
