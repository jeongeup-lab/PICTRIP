import { View, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { ScreenHeader } from "@/components/ScreenHeader";
import { ListGroup } from "@/components/ListGroup";
import { ListRow } from "@/components/ListRow";
import { LEGAL_DOCS } from "@/features/legal/constants";
import { colors, spacing } from "@/constants/theme";

export default function LegalListScreen() {
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScreenHeader title="약관·정책" fallback="/(tabs)/profile" />

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        <ListGroup style={styles.firstGroup}>
          {LEGAL_DOCS.map((doc) => (
            <ListRow
              key={doc.slug}
              title={doc.title}
              chevron
              onPress={() => router.push(`/legal/${doc.slug}`)}
              testID={`legal-${doc.slug}`}
            />
          ))}
        </ListGroup>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  scroll: { paddingBottom: spacing.xxl },
  firstGroup: { marginTop: spacing.md },
});
