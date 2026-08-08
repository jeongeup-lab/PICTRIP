import { useEffect, useRef, useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import { WebView, type WebViewMessageEvent } from "react-native-webview";
import { buildKakaoMapHtml } from "@/features/map/lib/kakao-map-html";
import { KAKAO_JS_KEY } from "@/constants/env";
import type { Bounds, LatLng } from "@/features/map/lib/geo";
import type { NearbySpot } from "@/lib/api-types";
import { colors, spacing } from "@/constants/theme";

export const KAKAO_WEB_ORIGIN = "https://localhost";

const ERROR_MESSAGES: Record<string, string> = {
  "missing-js-key": "지도 키가 설정되지 않았어요",
  "sdk-load-failed": "지도를 불러오지 못했어요. 네트워크를 확인해 주세요",
  "sdk-invalid": "지도 초기화에 실패했어요",
  "init-failed": "지도를 표시할 수 없어요",
};

export interface FitBounds {
  sw: LatLng;
  ne: LatLng;
  pad?: { top?: number; right?: number; bottom?: number; left?: number };
}

interface Props {
  center: LatLng | null;
  fit?: FitBounds | null;
  pins: NearbySpot[];
  selectedId?: string | null;
  anchorId?: string | null;
  userLocation: LatLng | null;
  onReady?: () => void;
  onPinTap: (contentId: string) => void;
  onViewportChange?: (center: LatLng, bounds: Bounds) => void;
  interactive?: boolean;
  accentDot?: boolean;
}

export function KakaoWebMap({
  center,
  fit = null,
  pins,
  selectedId = null,
  anchorId = null,
  userLocation,
  onReady,
  onPinTap,
  onViewportChange,
  interactive = true,
  accentDot = false,
}: Props) {
  const ref = useRef<WebView<object>>(null);
  const ready = useRef(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const send = (cmd: object) => {
    const json = JSON.stringify(cmd).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
    ref.current?.injectJavaScript(`window.handle({data:'${json}'});true;`);
  };

  useEffect(() => {
    if (ready.current && center) send({ cmd: "setCenter", lat: center.lat, lng: center.lng });
  }, [center]);
  useEffect(() => {
    if (ready.current && fit) send({ cmd: "fitBounds", ...fit });
  }, [fit]);
  useEffect(() => {
    if (ready.current)
      send({
        cmd: "setPins",
        spots: pins.map((p) => ({
          contentId: p.contentId,
          title: p.title,
          mapx: p.mapx,
          mapy: p.mapy,
          categoryGroup: p.categoryGroup,
        })),
      });
  }, [pins]);
  useEffect(() => {
    if (ready.current) send({ cmd: "setSelected", contentId: selectedId });
  }, [selectedId]);
  useEffect(() => {
    if (ready.current) send({ cmd: "setAnchor", contentId: anchorId });
  }, [anchorId]);
  useEffect(() => {
    if (ready.current)
      send({
        cmd: "setUserMarker",
        lat: userLocation?.lat ?? null,
        lng: userLocation?.lng ?? null,
      });
  }, [userLocation]);

  const onMessage = (e: WebViewMessageEvent) => {
    try {
      const m = JSON.parse(e.nativeEvent.data) as {
        type: string;
        payload?: Record<string, number | string>;
      };
      if (m.type === "ready") {
        ready.current = true;
        setLoadError(null);
        if (center) send({ cmd: "setCenter", lat: center.lat, lng: center.lng });
        if (fit) send({ cmd: "fitBounds", ...fit });
        send({
          cmd: "setPins",
          spots: pins.map((p) => ({
            contentId: p.contentId,
            title: p.title,
            mapx: p.mapx,
            mapy: p.mapy,
            categoryGroup: p.categoryGroup,
          })),
        });
        send({ cmd: "setSelected", contentId: selectedId });
        send({ cmd: "setAnchor", contentId: anchorId });
        send({
          cmd: "setUserMarker",
          lat: userLocation?.lat ?? null,
          lng: userLocation?.lng ?? null,
        });
        onReady?.();
      } else if (m.type === "error") {
        ready.current = false;
        const human = ERROR_MESSAGES[String(m.payload?.message)] ?? "지도를 불러오지 못했어요";
        const detail = m.payload?.detail ? `\n(${String(m.payload.detail)})` : "";
        setLoadError(human + detail);
      } else if (m.type === "pin_tap" && m.payload) {
        onPinTap(String(m.payload.contentId));
      } else if (m.type === "center_changed" && m.payload) {
        const p = m.payload;
        onViewportChange?.(
          { lat: Number(p.lat), lng: Number(p.lng) },
          {
            sw: { lat: Number(p.swLat), lng: Number(p.swLng) },
            ne: { lat: Number(p.neLat), lng: Number(p.neLng) },
          },
        );
      }
    } catch {}
  };

  if (!KAKAO_JS_KEY) {
    return (
      <View style={styles.placeholder}>
        <Text style={styles.placeholderText}>지도를 표시하려면 Kakao 지도 키가 필요해요</Text>
      </View>
    );
  }

  return (
    <View style={styles.web}>
      <WebView<object>
        ref={ref}
        style={styles.web}
        originWhitelist={["https://*", "http://*"]}
        source={{
          html: buildKakaoMapHtml(KAKAO_JS_KEY, { interactive, accentDot }),
          baseUrl: KAKAO_WEB_ORIGIN,
        }}
        onMessage={onMessage}
        javaScriptEnabled
        domStorageEnabled
        scrollEnabled={false}
      />
      {loadError ? (
        <View style={styles.errorOverlay} pointerEvents="none">
          <Text style={styles.placeholderText}>{loadError}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  web: { flex: 1, backgroundColor: colors.inset },
  errorOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.inset,
    padding: spacing.xl,
  },
  placeholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.inset,
    padding: spacing.xl,
  },
  placeholderText: { color: colors.ter, fontSize: 14, textAlign: "center" },
});
