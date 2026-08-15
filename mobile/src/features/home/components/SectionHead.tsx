import { StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "@/constants/theme";

interface Props {
  title: string;
  highlight?: string | null;
  caption?: string | null;
  note?: string | null;
}

export function SectionHead({ title, highlight, caption, note }: Props) {
  return (
    <View style={styles.head}>
      <View style={styles.row}>
        <View style={styles.titleRow}>
          {highlight ? (
            <Text
              testID="home-section-highlight"
              style={[styles.title, styles.highlight, styles.shrink]}
              numberOfLines={1}
              ellipsizeMode="tail"
            >
              {highlight}
            </Text>
          ) : null}
          <Text style={styles.title} numberOfLines={1}>
            {title}
          </Text>
        </View>
        {note ? (
          <Text testID="home-section-note" style={styles.note}>
            {note}
          </Text>
        ) : null}
      </View>
      {caption ? <Text style={styles.caption}>{caption}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  head: { paddingHorizontal: spacing.lg, paddingTop: spacing.xl, paddingBottom: spacing.md },
  row: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", gap: 8 },
  titleRow: { flex: 1, flexDirection: "row", alignItems: "baseline", minWidth: 0 },
  title: { fontSize: 20, fontWeight: "800", letterSpacing: -0.6, color: colors.ink },
  shrink: { flexShrink: 1 },
  highlight: { color: colors.accentText },
  note: { fontSize: 12, fontWeight: "600", color: colors.ter, paddingBottom: 2 },
  caption: { marginTop: 6, fontSize: 13.5, fontWeight: "500", color: colors.sec },
});
