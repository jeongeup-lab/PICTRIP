import { Linking } from "react-native";

export type RouteTarget = {
  title: string;
  lat: number | null;
  lng: number | null;
};

const NAVER_APP_NAME = "com.jeongeup.pictrip";

export function hasCoords(target: RouteTarget): boolean {
  return target.lat != null && target.lng != null;
}

export function kakaoRouteUrl(target: RouteTarget): string {
  const name = encodeURIComponent(target.title);
  return hasCoords(target)
    ? `https://map.kakao.com/link/to/${name},${target.lat},${target.lng}`
    : `https://map.kakao.com/link/search/${name}`;
}

export function naverAppUrl(target: RouteTarget): string {
  const name = encodeURIComponent(target.title);
  return hasCoords(target)
    ? `nmap://route/car?dlat=${target.lat}&dlng=${target.lng}&dname=${name}&appname=${NAVER_APP_NAME}`
    : `nmap://search?query=${name}`;
}

export function naverWebUrl(target: RouteTarget): string {
  return `https://map.naver.com/p/search/${encodeURIComponent(target.title)}`;
}

export function openKakaoRoute(target: RouteTarget): void {
  Linking.openURL(kakaoRouteUrl(target)).catch(() => {});
}

export function openNaverRoute(target: RouteTarget): void {
  Linking.openURL(naverAppUrl(target)).catch(() => {
    Linking.openURL(naverWebUrl(target)).catch(() => {});
  });
}
