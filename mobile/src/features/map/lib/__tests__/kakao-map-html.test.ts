import { buildKakaoMapHtml } from "@/features/map/lib/kakao-map-html";

describe("buildKakaoMapHtml", () => {
  const html = buildKakaoMapHtml("TESTKEY123");
  it("embeds the provided app key", () => {
    expect(html).toContain("appkey=TESTKEY123");
  });
  it("loads the SDK with autoload=false", () => {
    expect(html).toContain("dapi.kakao.com/v2/maps/sdk.js");
    expect(html).toContain("autoload=false");
    expect(html).toContain("kakao.maps.load");
  });
  it("wires the bridge message handlers", () => {
    expect(html).toContain("ReactNativeWebView");
    expect(html).toContain("center_changed");
    expect(html).toContain("pin_tap");
    expect(html).toContain("setPins");
  });
});
