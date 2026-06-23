import { View, Text, Pressable, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router, useLocalSearchParams } from "expo-router";
import { Icon } from "@/components/Icon";
import { LegalWebView } from "@/features/legal/components/LegalWebView";
import { findLegalDoc, legalUrl } from "@/features/legal/constants";
import { colors } from "@/constants/theme";

export default function LegalDocScreen() {
  const insets = useSafeAreaInsets();
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const doc = findLegalDoc(slug ?? "");

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Pressable style={styles.navBtn} onPress={() => router.back()} hitSlop={8}>
          <Icon name="chevron-left" size={23} />
        </Pressable>
        <Text style={styles.title} numberOfLines={1}>
          {doc?.title ?? "약관·정책"}
        </Text>
      </View>
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
  nav: {
    height: 50,
    flexDirection: "row",
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  navBtn: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  title: {
    position: "absolute",
    left: 44,
    right: 44,
    textAlign: "center",
    fontSize: 17,
    fontWeight: "700",
    color: colors.ink,
  },
  missing: { flex: 1, alignItems: "center", justifyContent: "center" },
  missingText: { fontSize: 15, color: colors.sec, fontWeight: "600" },
});
