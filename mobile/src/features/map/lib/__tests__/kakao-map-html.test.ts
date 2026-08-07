import {
  buildKakaoMapHtml,
  DARK_FILTER,
  PIN_ACCENT,
  PIN_INK,
  PIN_RESULT,
} from "@/features/map/lib/kakao-map-html";

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
  it("keeps the selected pin in the result pin's own shape", () => {
    expect(html).toContain("'pin anchor' : 'pin'");
    expect(html).not.toContain("tear");
  });

  it("marks the selection by recolouring the pin, not by drawing another one", () => {
    expect(html).toContain(`accent:${JSON.stringify(PIN_ACCENT)}`);
    expect(html).toContain("pin.style.background = C.accent");
  });

  it("still names the selected pin", () => {
    expect(html).toContain("lab.className='lab'");
  });

  it("hides the scale bar and keeps the Kakao attribution", () => {
    expect(html).toContain("$scale:false");
    expect(html).toContain("setCopyrightPosition");
  });

  it("holds the viewport inside Korea so no empty tiles show", () => {
    expect(html).toContain("KOREA_BOUNDS");
    expect(html).toContain("clampCenter");
    expect(html).toContain("setMaxLevel");
  });

  it("does not arm the clamp listeners when the map cannot be dragged", () => {
    const locked = buildKakaoMapHtml("TESTKEY123", { interactive: false });
    expect(locked).not.toContain("addListener(map,'drag',clampCenter)");
    expect(locked).not.toContain("setMaxLevel");
  });
  it("emits center_changed in the default (interactive) mode", () => {
    expect(buildKakaoMapHtml("TESTKEY123", { interactive: true })).toContain("center_changed");
  });
  it("locks the map and drops center_changed when non-interactive", () => {
    const locked = buildKakaoMapHtml("TESTKEY123", { interactive: false });
    expect(locked).toContain("setDraggable(false)");
    expect(locked).not.toContain("center_changed");
  });
  it("separates the result pins from the selected one by colour", () => {
    expect(html).toContain(`background:${PIN_INK}`);
    expect(html).toContain(PIN_ACCENT);
  });

  it("tints the generic pin dot with the accent color only when accentDot is set", () => {
    expect(buildKakaoMapHtml("TESTKEY123", { interactive: false, accentDot: true })).toContain(
      `var DOT = ${JSON.stringify(PIN_ACCENT)}`,
    );
    expect(buildKakaoMapHtml("TESTKEY123", { interactive: false })).toContain('var DOT = "#fff"');
  });

  it("inverts the basemap and inverts the overlays back when dark", () => {
    const darkHtml = buildKakaoMapHtml("TESTKEY123", { dark: true });
    expect(darkHtml).toContain(`#map{filter:${DARK_FILTER}}`);
    expect(darkHtml).toContain(`.pin,.sel,.me,#msg{filter:${DARK_FILTER}}`);
  });

  it("undoes the dark filter once per pin, even where a pin sits inside a wrapper", () => {
    expect(buildKakaoMapHtml("TESTKEY123", { dark: true })).toContain(".sel .pin{filter:none}");
  });

  it("leaves the basemap untouched when dark is off", () => {
    expect(buildKakaoMapHtml("TESTKEY123")).not.toContain("filter:");
  });

  it("draws the anchored place apart from the results it found", () => {
    expect(html).toContain("setAnchor");
    expect(html).toContain("pin anchor");
    expect(html).toContain(PIN_RESULT);
  });
});
