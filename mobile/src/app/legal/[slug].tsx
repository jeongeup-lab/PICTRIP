import { View, Text, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useLocalSearchParams } from "expo-router";
import { ScreenHeader } from "@/components/ScreenHeader";
import { LegalWebView } from "@/features/legal/components/LegalWebView";
import { findLegalDoc, legalUrl } from "@/features/legal/constants";
import { colors } from "@/constants/theme";

export default function LegalDocScreen() {
  const insets = useSafeAreaInsets();
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const doc = findLegalDoc(slug ?? "");

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScreenHeader title={doc?.title ?? "약관·정책"} fallback="/legal" />
      {doc ? (
        <LegalWebView url={legalUrl(doc.slug)} />
      ) : (
        <View style={styles.missing}>
          <Text style={styles.missingText}>문서를 찾을 수 없어요</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  missing: { flex: 1, alignItems: "center", justifyContent: "center" },
  missingText: { fontSize: 15, color: colors.sec, fontWeight: "600" },
});
