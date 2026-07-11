import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { LEGAL_DOCS } from "@/features/legal/constants";
import { colors, spacing } from "@/constants/theme";

export default function LegalListScreen() {
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Pressable style={styles.navBtn} onPress={() => router.back()} hitSlop={8}>
          <Icon name="chevron-left" size={23} />
        </Pressable>
        <Text style={styles.title}>약관·정책</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false}>
        <View style={styles.group}>
          {LEGAL_DOCS.map((doc) => (
            <Pressable
              key={doc.slug}
              style={styles.row}
              onPress={() => router.push(`/legal/${doc.slug}`)}
            >
              <Text style={styles.rowLabel}>{doc.title}</Text>
              <Icon name="chevron-right" size={20} color={colors.ter} />
            </Pressable>
          ))}
        </View>
      </ScrollView>
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
    left: 0,
    right: 0,
    textAlign: "center",
    fontSize: 17,
    fontWeight: "700",
    color: colors.ink,
  },
  group: { backgroundColor: colors.bg, marginTop: 8 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 17,
    paddingHorizontal: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  rowLabel: { flex: 1, fontSize: 15.5, fontWeight: "600", color: colors.ink },
});
