import { homeKeys } from "@/features/home/queries";

const SEOUL = { lat: 37.5401, lng: 127.0695 };

describe("homeKeys.recommendations", () => {
  it("scopes the cache to the signed-in account", () => {
    expect(homeKeys.recommendations(7, SEOUL)).not.toEqual(homeKeys.recommendations(8, SEOUL));
  });

  it("separates a signed-out reader from any account", () => {
    expect(homeKeys.recommendations(null, SEOUL)).not.toEqual(homeKeys.recommendations(7, SEOUL));
  });

  it("still splits one account across distant coordinates", () => {
    expect(homeKeys.recommendations(7, SEOUL)).not.toEqual(
      homeKeys.recommendations(7, { lat: 35.1595, lng: 129.0756 }),
    );
  });

  it("shares the root with the key the sign-out and save paths evict", () => {
    expect(homeKeys.recommendations(7, SEOUL)[0]).toBe(homeKeys.recommendationsRoot[0]);
  });
});
