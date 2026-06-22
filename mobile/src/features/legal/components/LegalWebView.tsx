import { useRef, useState } from "react";
import { View, Text, Pressable, ActivityIndicator, StyleSheet } from "react-native";
import { WebView, type WebViewNavigation } from "react-native-webview";
import * as WebBrowser from "expo-web-browser";
import { colors, spacing } from "@/constants/theme";
import { LEGAL_BASE_URL } from "@/features/legal/constants";

/** In-app document viewer (S06 D1/D3). Loads only pictrip.org/legal/* in the
 * WebView; any other navigation opens in the system browser. On load failure,
 * offers retry + open-in-browser. */
export function LegalWebView({ url }: { url: string }) {
  // react-native-webview 14's `WebView<P = undefined>` collapses its props to
  // `never` under React 19's JSX typing; instantiating the generic as `<object>`
  // resolves `WebViewProps & object` back to `WebViewProps`. Runtime unchanged.
  const ref = useRef<WebView<object>>(null);
  const [loading, setLoading] = useState(true);
  const [errored, setErrored] = useState(false);

  const retry = () => {
    setErrored(false);
    setLoading(true);
    ref.current?.reload();
  };

  const onShouldStart = (req: WebViewNavigation): boolean => {
    if (req.url.startsWith(LEGAL_BASE_URL)) return true;
    void WebBrowser.openBrowserAsync(req.url);
    return false;
  };

  if (errored) {
    return (
      <View style={styles.center}>
        <Text style={styles.errText}>불러오지 못했어요</Text>
        <View style={styles.errActions}>
          <Pressable style={styles.btn} onPress={retry} hitSlop={8}>
            <Text style={styles.btnText}>재시도</Text>
          </Pressable>
          <Pressable
            style={styles.btn}
            onPress={() => void WebBrowser.openBrowserAsync(url)}
            hitSlop={8}
          >
            <Text style={styles.btnText}>브라우저로 열기</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.fill}>
      <WebView<object>
        ref={ref}
        source={{ uri: url }}
        originWhitelist={[`${LEGAL_BASE_URL}/*`]}
        onShouldStartLoadWithRequest={onShouldStart}
        onLoadStart={() => setLoading(true)}
        onLoadEnd={() => setLoading(false)}
        onError={() => {
          setLoading(false);
          setErrored(true);
        }}
        onHttpError={() => {
          setLoading(false);
          setErrored(true);
        }}
      />
      {loading ? (
        <View style={styles.loadingOverlay} pointerEvents="none">
          <ActivityIndicator color={colors.sec} />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: colors.bg },
  loadingOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.bg,
  },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.bg,
    gap: spacing.lg,
  },
  errText: { fontSize: 15, color: colors.sec, fontWeight: "600" },
  errActions: { flexDirection: "row", gap: spacing.md },
  btn: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.line,
  },
  btnText: { fontSize: 14, color: colors.ink, fontWeight: "600" },
});
