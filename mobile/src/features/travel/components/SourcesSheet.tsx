import { Linking, Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Icon, type IconName } from "@/components/Icon";
import type { SourceItem, SourceKind } from "@/features/travel/api";
import { colors, radii, spacing } from "@/constants/theme";

export const SOURCES_TITLE = "소스";
export const KTO_SOURCE_TITLE = "한국관광공사 TourAPI";
export const KTO_SOURCE_NOTE = "관광지 정보 출처";

export const KIND_ICONS: Record<SourceKind, IconName> = {
  naver_blog: "globe",
  kto: "shield-check",
  kakao: "map-pin",
};

export function formatSourceDate(date: string | null | undefined): string | null {
  if (!date) return null;
  const compact = /^(\d{4})(\d{2})(\d{2})$/.exec(date);
  if (compact) return `${compact[1]}.${compact[2]}.${compact[3]}`;
  const iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(date);
  if (iso) return `${iso[1]}.${iso[2]}.${iso[3]}`;
  return date;
}

interface Props {
  visible: boolean;
  items: SourceItem[];
  onClose: () => void;
}

function SourceRow({ item }: { item: SourceItem }) {
  const date = formatSourceDate(item.date);
  const url = item.url ?? null;
  return (
    <Pressable
      testID="travel-source-row"
      accessibilityRole={url ? "link" : "text"}
      style={({ pressed }) => [styles.row, pressed && url !== null && styles.pressed]}
      disabled={!url}
      onPress={() => {
        if (url) void Linking.openURL(url);
      }}
    >
      <View style={styles.kindBadge}>
        <Icon
          name={KIND_ICONS[item.kind] ?? "globe"}
          size={14}
          color={colors.sec}
          strokeWidth={1.9}
        />
      </View>
      <View style={styles.copy}>
        <Text style={styles.rowTitle} numberOfLines={2}>
          {item.title}
        </Text>
        {date ? <Text style={styles.rowNote}>{date}</Text> : null}
      </View>
      {url ? <Icon name="chevron-right" size={14} color={colors.ter} strokeWidth={2} /> : null}
    </Pressable>
  );
}

export function SourcesSheet({ visible, items, onClose }: Props) {
  const insets = useSafeAreaInsets();
  const listed = items.filter((item) => item.kind !== "kto");

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.scrim} onPress={onClose}>
        <Pressable
          style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }]}
          onPress={(e) => e.stopPropagation()}
        >
          <View style={styles.grabber} />
          <Text style={styles.title}>{SOURCES_TITLE}</Text>
          {listed.map((item, index) => (
            <SourceRow key={`${index}-${item.title}`} item={item} />
          ))}
          <View testID="travel-source-kto" style={styles.row}>
            <View style={styles.kindBadge}>
              <Icon name={KIND_ICONS.kto} size={14} color={colors.sec} strokeWidth={1.9} />
            </View>
            <View style={styles.copy}>
              <Text style={styles.rowTitle}>{KTO_SOURCE_TITLE}</Text>
              <Text style={styles.rowNote}>{KTO_SOURCE_NOTE}</Text>
            </View>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: { flex: 1, justifyContent: "flex-end", backgroundColor: colors.scrim },
  sheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: radii.xl,
    borderTopRightRadius: radii.xl,
    paddingTop: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  grabber: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.line,
    marginBottom: spacing.md,
  },
  title: { fontSize: 18, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  pressed: { opacity: 0.7 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 13,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  kindBadge: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.fill,
  },
  copy: { flex: 1, minWidth: 0 },
  rowTitle: { fontSize: 14, fontWeight: "600", letterSpacing: -0.2, color: colors.ink },
  rowNote: { marginTop: 2, fontSize: 12, color: colors.ter },
});
