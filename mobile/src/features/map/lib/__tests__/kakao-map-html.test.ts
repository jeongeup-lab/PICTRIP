import { buildKakaoMapHtml } from "@/features/map/lib/kakao-map-html";

describe("buildKakaoMapHtml", () => {
  const html = buildKakaoMapHtml("TESTKEY123");
  it("embeds the provided app key", () => {
    // Key is injected as a JS string literal and concatenated into the SDK URL
    // at runtime (dynamic <script> load surfaces network/domain failures).
    expect(html).toContain('"TESTKEY123"');
    expect(html).toContain("appkey=' + key +");
  });
  it("loads the SDK with autoload=false", () => {
    expect(html).toContain("dapi.kakao.com/v2/maps/sdk.js");
    expect(html).toContain("autoload=false");
    expect(html).toContain("kakao.maps.load");
  });
  it("surfaces SDK load failures", () => {
    expect(html).toContain("sdk-load-failed");
    expect(html).toContain("s.onerror");
  });
  it("wires the bridge message handlers", () => {
    expect(html).toContain("ReactNativeWebView");
    expect(html).toContain("center_changed");
    expect(html).toContain("pin_tap");
    expect(html).toContain("setPins");
  });
  it("emits center_changed in the default (interactive) mode", () => {
    expect(buildKakaoMapHtml("TESTKEY123", true)).toContain("center_changed");
  });
  it("locks the map and drops center_changed when non-interactive", () => {
    // Locked map lives inside a scrolling page (spot detail) — no drag, no events.
    const locked = buildKakaoMapHtml("TESTKEY123", false);
    expect(locked).toContain("setDraggable(false)");
    expect(locked).not.toContain("center_changed");
  });
});
