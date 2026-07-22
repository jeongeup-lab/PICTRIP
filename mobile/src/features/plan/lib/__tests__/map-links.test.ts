import { Linking } from "react-native";
import {
  kakaoRouteUrl,
  naverAppUrl,
  naverWebUrl,
  openNaverRoute,
} from "@/features/plan/lib/map-links";

const target = { title: "동피랑 벽화마을", lat: 34.8422, lng: 128.4239 };

describe("kakaoRouteUrl", () => {
  it("builds a route link with coordinates", () => {
    expect(kakaoRouteUrl(target)).toBe(
      `https://map.kakao.com/link/to/${encodeURIComponent(target.title)},34.8422,128.4239`,
    );
  });

  it("falls back to a name search when the spot has no coordinates", () => {
    expect(kakaoRouteUrl({ title: "동피랑", lat: null, lng: null })).toContain("/link/search/");
  });
});

describe("naverAppUrl", () => {
  it("builds a car-route deep link carrying the app identifier", () => {
    const url = naverAppUrl(target);
    expect(url).toContain("nmap://route/car?dlat=34.8422&dlng=128.4239");
    expect(url).toContain("appname=com.jeongeup.pictrip");
  });
});

describe("openNaverRoute", () => {
  afterEach(() => jest.restoreAllMocks());

  it("falls back to the naver web map when the app scheme is not installed", async () => {
    const openURL = jest
      .spyOn(Linking, "openURL")
      .mockRejectedValueOnce(new Error("no handler"))
      .mockResolvedValueOnce(true);

    openNaverRoute(target);
    await new Promise(process.nextTick);

    expect(openURL).toHaveBeenNthCalledWith(1, naverAppUrl(target));
    expect(openURL).toHaveBeenNthCalledWith(2, naverWebUrl(target));
  });
});
