import { buildKakaoMapHtml, PIN_ACCENT } from "@/features/map/lib/kakao-map-html";

describe("buildKakaoMapHtml", () => {
  const html = buildKakaoMapHtml("TESTKEY123");
  it("embeds the provided app key", () => {
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
    expect(html).toContain("setSelected");
  });
  it("renders the selected pin with an accent dot and a title label chip", () => {
    expect(html).toContain("el.className='sel'");
    expect(html).toContain('class="lab"');
    expect(html).toContain('circle cx="12" cy="10.5" r="2.6" fill="#E60023"');
  });
  it("emits center_changed in the default (interactive) mode", () => {
    expect(buildKakaoMapHtml("TESTKEY123", true)).toContain("center_changed");
  });
  it("locks the map and drops center_changed when non-interactive", () => {
    const locked = buildKakaoMapHtml("TESTKEY123", false);
    expect(locked).toContain("setDraggable(false)");
    expect(locked).not.toContain("center_changed");
  });
  it("paints every pin accent red when the caller asks for it", () => {
    const accent = buildKakaoMapHtml("TESTKEY123", false, false, PIN_ACCENT);

    expect(accent).toContain("background:#E60023");
    expect(accent).toContain('class="tear" viewBox="0 0 24 24" fill="#E60023"');
    expect(accent).toContain('circle cx="12" cy="10.5" r="2.6" fill="#FFFFFF"');
  });

  it("keeps the ink pin as the default", () => {
    const html = buildKakaoMapHtml("TESTKEY123");

    expect(html).toContain("background:#171719");
    expect(html).toContain('class="tear" viewBox="0 0 24 24" fill="#171719"');
  });

  it("tints the generic pin dot with the accent color only when accentDot is set", () => {
    expect(buildKakaoMapHtml("TESTKEY123", false, true)).toContain('var DOT = "#E60023"');
    expect(buildKakaoMapHtml("TESTKEY123", false)).toContain('var DOT = "#fff"');
  });
});
