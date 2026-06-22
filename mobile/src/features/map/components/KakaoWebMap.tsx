import { useEffect, useRef } from "react";
import { View, Text, StyleSheet } from "react-native";
import { WebView, type WebViewMessageEvent } from "react-native-webview";
import { buildKakaoMapHtml } from "@/features/map/lib/kakao-map-html";
import { KAKAO_JS_KEY } from "@/constants/env";
import type { LatLng } from "@/features/map/lib/geo";
import type { NearbySpot } from "@/lib/api-types";
import { colors, spacing } from "@/constants/theme";

interface Props {
  center: LatLng | null;
  pins: NearbySpot[];
  userLocation: LatLng | null;
  onReady?: () => void;
  onPinTap: (contentId: string) => void;
  onCenterChanged: (c: LatLng) => void;
}

export function KakaoWebMap({
  center,
  pins,
  userLocation,
  onReady,
  onPinTap,
  onCenterChanged,
}: Props) {
  // react-native-webview 14's `WebView<P = undefined>` collapses its props to
  // `never` under React 19's JSX typing; instantiating the generic as `<object>`
  // resolves `WebViewProps & object` back to `WebViewProps`. Runtime unchanged.
  const ref = useRef<WebView<object>>(null);
  const ready = useRef(false);

  const send = (cmd: object) => {
    // Escape backslash first, then single quote: JSON.stringify leaves `'`
    // unescaped, which would break out of the single-quoted JS string literal.
    const json = JSON.stringify(cmd).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
    ref.current?.injectJavaScript(`window.handle({data:'${json}'});true;`);
  };

  useEffect(() => {
    if (ready.current && center) send({ cmd: "setCenter", lat: center.lat, lng: center.lng });
  }, [center]);
  useEffect(() => {
    if (ready.current)
      send({
        cmd: "setPins",
        spots: pins.map((p) => ({ contentId: p.contentId, mapx: p.mapx, mapy: p.mapy })),
      });
  }, [pins]);
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
        if (center) send({ cmd: "setCenter", lat: center.lat, lng: center.lng });
        send({
          cmd: "setPins",
          spots: pins.map((p) => ({ contentId: p.contentId, mapx: p.mapx, mapy: p.mapy })),
        });
        send({
          cmd: "setUserMarker",
          lat: userLocation?.lat ?? null,
          lng: userLocation?.lng ?? null,
        });
        onReady?.();
      } else if (m.type === "pin_tap" && m.payload) {
        onPinTap(String(m.payload.contentId));
      } else if (m.type === "center_changed" && m.payload) {
        onCenterChanged({ lat: Number(m.payload.lat), lng: Number(m.payload.lng) });
      }
    } catch {
      // ignore malformed bridge messages
    }
  };

  // Graceful degrade: no JS key → blank placeholder (list/permission/picker still work).
  if (!KAKAO_JS_KEY) {
    return (
      <View style={styles.placeholder}>
        <Text style={styles.placeholderText}>지도를 표시하려면 Kakao 지도 키가 필요해요</Text>
      </View>
    );
  }

  return (
    <WebView<object>
      ref={ref}
      style={styles.web}
      originWhitelist={["*"]}
      source={{ html: buildKakaoMapHtml(KAKAO_JS_KEY) }}
      onMessage={onMessage}
      javaScriptEnabled
      domStorageEnabled
      scrollEnabled={false}
    />
  );
}

const styles = StyleSheet.create({
  web: { flex: 1, backgroundColor: colors.inset },
  placeholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.inset,
    padding: spacing.xl,
  },
  placeholderText: { color: colors.ter, fontSize: 14, textAlign: "center" },
});
