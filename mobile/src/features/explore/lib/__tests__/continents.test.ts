import {
  CONTINENTS,
  continentOf,
  continentsPresent,
  filterByContinent,
} from "@/features/explore/lib/continents";
import type { OverseasPost } from "@/features/explore/api";

function post(id: number, countryCode: string): OverseasPost {
  return {
    id,
    nameKo: `장소 ${id}`,
    countryCode,
    countryNameKo: countryCode,
    descriptionKo: null,
    imageUrl: `https://upload.wikimedia.org/${id}.jpg`,
    imageAuthor: null,
    imageLicense: null,
    imageLicenseUrl: null,
    imageSourceUrl: `https://commons.wikimedia.org/${id}`,
    matches: [],
  };
}

describe("continents", () => {
  it("maps country codes onto continents", () => {
    expect(continentOf("JP")).toBe("아시아");
    expect(continentOf("FR")).toBe("유럽");
    expect(continentOf("US")).toBe("아메리카");
    expect(continentOf("AU")).toBe("오세아니아");
    expect(continentOf("EG")).toBe("아프리카");
  });

  it("accepts lowercase codes", () => {
    expect(continentOf("kr")).toBe("아시아");
  });

  it("returns null for missing or unknown codes", () => {
    expect(continentOf(null)).toBeNull();
    expect(continentOf("")).toBeNull();
    expect(continentOf("ZZ")).toBeNull();
  });

  it("puts the countries that straddle two continents where travellers look for them", () => {
    expect(continentOf("TR")).toBe("유럽");
    expect(continentOf("RU")).toBe("유럽");
    expect(continentOf("GE")).toBe("유럽");
    expect(continentOf("MX")).toBe("아메리카");
    expect(continentOf("EG")).toBe("아프리카");
  });

  it("offers five continents", () => {
    expect(CONTINENTS).toHaveLength(5);
  });

  it("filters by continent and keeps everything when none is picked", () => {
    const posts = [post(1, "JP"), post(2, "FR"), post(3, "IT"), post(4, "ZZ")];
    expect(filterByContinent(posts, null)).toHaveLength(4);
    expect(filterByContinent(posts, "유럽").map((p) => p.id)).toEqual([2, 3]);
    expect(filterByContinent(posts, "아프리카")).toHaveLength(0);
  });

  it("lists only the continents present, in a stable order", () => {
    const posts = [post(1, "EG"), post(2, "JP"), post(3, "FR"), post(4, "ZZ")];
    expect(continentsPresent(posts)).toEqual(["유럽", "아시아", "아프리카"]);
  });

  it("drops unmapped codes from the chip list", () => {
    expect(continentsPresent([post(1, "ZZ")])).toEqual([]);
  });
});
