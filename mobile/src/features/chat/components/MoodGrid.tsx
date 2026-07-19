import { View, Text, Pressable, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, radii, spacing } from "@/constants/theme";

interface Mood {
  label: string;
  sub: string;
  utterance: string;
}

const MOODS: Mood[] = [
  { label: "바다 · 트임", sub: "수평선, 바람", utterance: "바다가 보이는 탁 트인 곳" },
  { label: "숲 · 고요", sub: "그늘, 흙길", utterance: "숲이 우거진 고요한 곳" },
  { label: "골목 · 감성", sub: "간판, 낮은 지붕", utterance: "골목 감성이 있는 곳" },
  { label: "야경 · 도심", sub: "불빛, 리듬", utterance: "야경이 멋진 도심" },
];

interface Props {
  onPick: (utterance: string) => void;
  onPhoto: () => void;
  disabled?: boolean;
}

export function MoodGrid({ onPick, onPhoto, disabled }: Props) {
  return (
    <View style={styles.wrap}>
      <View style={styles.grid}>
        {MOODS.map((m) => (
          <Pressable
            key={m.label}
            style={styles.tile}
            disabled={disabled}
            onPress={() => onPick(m.utterance)}
          >
            <Text style={styles.tileLabel}>{m.label}</Text>
            <Text style={styles.tileSub}>{m.sub}</Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.orRow}>
        <View style={styles.orLine} />
        <Text style={styles.orText}>또는</Text>
        <View style={styles.orLine} />
      </View>

      <Pressable style={styles.photo} disabled={disabled} onPress={onPhoto}>
        <View style={styles.photoIcon}>
          <Icon name="image" size={24} color={colors.ink} />
        </View>
        <View style={styles.photoText}>
          <Text style={styles.photoLabel}>내 사진으로 시작</Text>
          <Text style={styles.photoSub}>
            끌리는 사진 한 장을 올리면, 그 결에서 첫 후보를 열어요
          </Text>
        </View>
        <View style={styles.photoGo}>
          <Icon name="chevron-right" size={16} color={colors.onImage} />
        </View>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.md },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  tile: {
    width: "47%",
    flexGrow: 1,
    minHeight: 92,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.inset,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    justifyContent: "flex-end",
    gap: 3,
  },
  tileLabel: { fontSize: 15.5, fontWeight: "800", color: colors.ink, letterSpacing: -0.3 },
  tileSub: { fontSize: 11, fontWeight: "600", color: colors.ter },
  orRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  orLine: { flex: 1, height: 1, backgroundColor: colors.line },
  orText: { fontSize: 11, fontWeight: "700", color: colors.ter },
  photo: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderRadius: radii.lg,
    borderWidth: 1.5,
    borderStyle: "dashed",
    borderColor: colors.line,
    backgroundColor: colors.bg,
    padding: spacing.md,
  },
  photoIcon: {
    width: 50,
    height: 50,
    borderRadius: radii.lg,
    backgroundColor: colors.inset,
    alignItems: "center",
    justifyContent: "center",
  },
  photoText: { flex: 1, minWidth: 0 },
  photoLabel: { fontSize: 14.5, fontWeight: "800", color: colors.ink, letterSpacing: -0.2 },
  photoSub: { marginTop: 3, fontSize: 12, lineHeight: 17, color: colors.sec },
  photoGo: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.ink,
    alignItems: "center",
    justifyContent: "center",
  },
});
