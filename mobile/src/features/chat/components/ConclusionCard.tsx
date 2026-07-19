import { View, Text, Pressable, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { colors, radii, spacing } from "@/constants/theme";
import type { ChatCard } from "@/features/chat/types";

interface Props {
  title: string;
  summary: string;
  spots: ChatCard[];
  onOpenSpot: (contentId: string) => void;
  onMap: () => void;
  onRestart: () => void;
}

export function ConclusionCard({ title, summary, spots, onOpenSpot, onMap, onRestart }: Props) {
  return (
    <View style={styles.card}>
      <View style={styles.tag}>
        <Text style={styles.tagText}>오늘의 결론</Text>
      </View>
      <Text style={styles.title}>{title}</Text>
      {summary ? <Text style={styles.summary}>{summary}</Text> : null}

      <View style={styles.rows}>
        {spots.map((s) => {
          const meta = [s.regionLabel, s.category].filter(Boolean).join(" · ");
          return (
            <Pressable key={s.contentId} style={styles.row} onPress={() => onOpenSpot(s.contentId)}>
              <RemoteImage uri={s.firstImageUrl} radius={radii.md} style={styles.rowImg} />
              <View style={styles.rowText}>
                <Text numberOfLines={1} style={styles.rowName}>
                  {s.title}
                </Text>
                {meta ? (
                  <Text numberOfLines={1} style={styles.rowMeta}>
                    {meta}
                  </Text>
                ) : null}
                {s.why ? (
                  <Text numberOfLines={1} style={styles.rowWhy}>
                    {s.why}
                  </Text>
                ) : null}
              </View>
              <Icon name="chevron-right" size={16} color={colors.ter} />
            </Pressable>
          );
        })}
      </View>

      <View style={styles.cta}>
        <Pressable style={[styles.btn, styles.btnPri]} onPress={onMap}>
          <Icon name="map-pin" size={15} color={colors.onImage} />
          <Text style={styles.btnPriText}>지도로 한눈에 보기</Text>
        </Pressable>
        <Pressable style={[styles.btn, styles.btnGhost]} onPress={onRestart}>
          <Text style={styles.btnGhostText}>새로운 스무고개 시작</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bg,
    borderRadius: 20,
    padding: spacing.lg,
    shadowColor: "#171719",
    shadowOpacity: 0.08,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  },
  tag: {
    alignSelf: "flex-start",
    paddingHorizontal: 11,
    paddingVertical: 4,
    borderRadius: radii.pill,
    backgroundColor: colors.accentFill,
  },
  tagText: { fontSize: 10.5, fontWeight: "800", color: colors.accentText },
  title: {
    marginTop: 9,
    fontSize: 20,
    fontWeight: "800",
    color: colors.ink,
    letterSpacing: -0.5,
  },
  summary: { marginTop: 3, fontSize: 12.5, color: colors.ter },
  rows: { marginTop: spacing.md },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 13,
    paddingVertical: 11,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  rowImg: { width: 58, height: 58, backgroundColor: colors.inset },
  rowText: { flex: 1, minWidth: 0 },
  rowName: { fontSize: 15, fontWeight: "800", color: colors.ink, letterSpacing: -0.2 },
  rowMeta: { marginTop: 1, fontSize: 12, color: colors.ter },
  rowWhy: { marginTop: 2, fontSize: 11.5, color: colors.sec },
  cta: { marginTop: spacing.md, gap: spacing.sm },
  btn: {
    height: 48,
    borderRadius: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
  },
  btnPri: { backgroundColor: colors.ink },
  btnPriText: { fontSize: 14.5, fontWeight: "800", color: colors.onImage },
  btnGhost: { backgroundColor: colors.inset },
  btnGhostText: { fontSize: 14.5, fontWeight: "800", color: colors.ink },
});
