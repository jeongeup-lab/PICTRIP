import type { OverseasPost } from "@/features/explore/api";

export const CONTINENTS = ["유럽", "아시아", "아메리카", "오세아니아", "아프리카"] as const;

export type Continent = (typeof CONTINENTS)[number];

const CODES: Record<Continent, string> = {
  유럽:
    "AD AL AT AX BA BE BG BY CH CY CZ DE DK EE ES FI FO FR GB GE GG GI GR HR HU IE IM IS IT " +
    "JE LI LT LU LV MC MD ME MK MT NL NO PL PT RO RS RU SE SI SJ SK SM TR UA VA XK",
  아시아:
    "AE AF AM AZ BD BH BN BT CN HK ID IL IN IQ IR JO JP KG KH KP KR KW KZ LA LB LK MM MN MO " +
    "MV MY NP OM PH PK PS QA SA SG SY TH TJ TL TM TW UZ VN YE",
  아메리카:
    "AG AI AR AW BB BL BM BO BQ BR BS BZ CA CL CO CR CU CW DM DO EC FK GD GF GL GP GT GY HN " +
    "HT JM KN KY LC MF MQ MS MX NI PA PE PM PR PY SR SV SX TC TT US UY VC VE VG VI",
  오세아니아: "AS AU CK FJ FM GU KI MH MP NC NF NR NU NZ PF PG PN PW SB TK TO TV VU WF WS",
  아프리카:
    "AO BF BI BJ BW CD CF CG CI CM CV DJ DZ EG EH ER ET GA GH GM GN GQ GW KE KM LR LS LY MA " +
    "MG ML MR MU MW MZ NA NE NG RE RW SC SD SH SL SN SO SS ST SZ TD TG TN TZ UG YT ZA ZM ZW",
};

const LOOKUP: ReadonlyMap<string, Continent> = new Map(
  CONTINENTS.flatMap((continent) =>
    CODES[continent].split(" ").map((code) => [code, continent] as [string, Continent]),
  ),
);

export function continentOf(countryCode: string | null | undefined): Continent | null {
  if (!countryCode) return null;
  return LOOKUP.get(countryCode.toUpperCase()) ?? null;
}

export function filterByContinent(
  posts: OverseasPost[],
  continent: Continent | null,
): OverseasPost[] {
  if (continent === null) return posts;
  return posts.filter((post) => continentOf(post.countryCode) === continent);
}

export function continentsPresent(posts: OverseasPost[]): Continent[] {
  const found = new Set(
    posts.map((post) => continentOf(post.countryCode)).filter((c): c is Continent => c !== null),
  );
  return CONTINENTS.filter((continent) => found.has(continent));
}
