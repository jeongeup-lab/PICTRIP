import { useCallback, useEffect, useMemo, useRef } from "react";
import { View, StyleSheet } from "react-native";
import { WebView } from "react-native-webview";
import { KAKAO_JS_KEY } from "@/constants/env";
import { KAKAO_WEB_ORIGIN } from "@/features/map/components/KakaoWebMap";
import { buildPlanRouteHtml, type RoutePoint } from "@/features/plan/lib/plan-route-html";
import { colors, radii } from "@/constants/theme";

interface Props {
  points: RoutePoint[];
}

export function PlanRouteMap({ points }: Props) {
  const ref = useRef<WebView<object>>(null);
  const html = useMemo(() => buildPlanRouteHtml(KAKAO_JS_KEY), []);

  const send = useCallback(() => {
    const json = JSON.stringify({ cmd: "setRoute", points })
      .replace(/\\/g, "\\\\")
      .replace(/'/g, "\\'");
    ref.current?.injectJavaScript(`window.handle({data:'${json}'});true;`);
  }, [points]);

  useEffect(() => send(), [send]);

  if (!KAKAO_JS_KEY || points.length < 2) return null;

  return (
    <View style={styles.card}>
      <WebView<object>
        ref={ref}
        style={styles.web}
        originWhitelist={["https://*", "http://*"]}
        source={{ html, baseUrl: KAKAO_WEB_ORIGIN }}
        onLoadEnd={send}
        javaScriptEnabled
        domStorageEnabled
        scrollEnabled={false}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    height: 170,
    marginTop: 10,
    borderRadius: radii.lg,
    overflow: "hidden",
    backgroundColor: colors.inset,
  },
  web: { flex: 1, backgroundColor: colors.inset },
});
