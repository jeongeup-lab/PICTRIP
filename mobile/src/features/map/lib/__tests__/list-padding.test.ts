import { mapListPaddingBottom } from "../list-padding";

describe("mapListPaddingBottom", () => {
  const tabBar = 83;
  const margin = 32;

  it("clears the off-screen sheet overflow + tab bar at every snap", () => {
    const overflowBySnap = { full: 0.08 * 844, half: 0.42 * 844, peek: 0.88 * 844 };
    for (const overflow of Object.values(overflowBySnap)) {
      expect(mapListPaddingBottom(overflow, tabBar, margin)).toBeGreaterThanOrEqual(
        overflow + tabBar,
      );
    }
  });

  it("scales with the snap's off-screen overflow (half needs more than full)", () => {
    const half = mapListPaddingBottom(0.42 * 844, tabBar, margin);
    const full = mapListPaddingBottom(0.08 * 844, tabBar, margin);
    expect(half).toBeGreaterThan(full);
  });
});
