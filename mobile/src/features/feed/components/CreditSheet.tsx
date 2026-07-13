import { Modal, Pressable, View, Text, Linking, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { OverseasPost } from "@/features/feed/posts-api";
import { colors, spacing, radii } from "@/constants/theme";

interface Props {
  visible: boolean;
  post: OverseasPost;
  onClose: () => void;
}

export function CreditSheet({ visible, post, onClose }: Props) {
  const insets = useSafeAreaInsets();

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.scrim} onPress={onClose}>
        <Pressable
          style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }]}
          onPress={(e) => e.stopPropagation()}
        >
          <View style={styles.grabber} />
          <Text style={styles.title}>사진 정보</Text>

          <Row label="촬영" value={post.imageAuthor ?? "-"} />
          <LinkRow label="라이선스" value={post.imageLicense ?? "-"} url={post.imageLicenseUrl} />
          <LinkRow label="제공" value="Wikimedia Commons" url={post.imageSourceUrl} />
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue} numberOfLines={1}>
        {value}
      </Text>
    </View>
  );
}

function LinkRow({ label, value, url }: { label: string; value: string; url: string | null }) {
  const disabled = !url;
  return (
    <Pressable
      testID={`credit-link-${label}`}
      style={styles.row}
      disabled={disabled}
      onPress={() => {
        if (url) void Linking.openURL(url);
      }}
    >
      <Text style={styles.rowLabel}>{label}</Text>
      <View style={styles.rowRight}>
        <Text style={[styles.rowValue, disabled && styles.rowValueDisabled]} numberOfLines={1}>
          {value}
        </Text>
        {!disabled ? (
          <Text style={styles.arrow} accessibilityLabel="열기">
            ↗
          </Text>
        ) : null}
      </View>
    </Pressable>
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
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  rowLabel: { fontSize: 14, fontWeight: "700", color: colors.sec },
  rowRight: { flexDirection: "row", alignItems: "center", gap: 6, flexShrink: 1 },
  rowValue: { fontSize: 14.5, fontWeight: "600", color: colors.ink, flexShrink: 1 },
  rowValueDisabled: { color: colors.ter },
  arrow: { fontSize: 15, fontWeight: "700", color: colors.accentText },
});
