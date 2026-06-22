import { useEffect, useState } from "react";
import { Modal, View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Icon } from "@/components/Icon";
import { Skeleton } from "@/components/Skeleton";
import { useRegionsTree } from "@/features/map/queries";
import type { Centroid, RegionNode } from "@/lib/api-types";
import { colors, spacing, radii } from "@/constants/theme";

interface Props {
  visible: boolean;
  onClose: () => void;
  onApply: (centroid: Centroid, regionName: string) => void;
}

export function RegionPicker({ visible, onClose, onApply }: Props) {
  const insets = useSafeAreaInsets();
  const { data: tree, isLoading, isError, refetch } = useRegionsTree();
  const [sidoIdx, setSidoIdx] = useState(0);
  // selection: null = "{시도} 전체", else sigungu index
  const [sigunguIdx, setSigunguIdx] = useState<number | null>(null);

  useEffect(() => {
    if (visible) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reset transient picker selection each time the sheet opens.
      setSidoIdx(0);
      setSigunguIdx(null);
    }
  }, [visible]);

  const sido: RegionNode | undefined = tree?.[sidoIdx];

  const apply = () => {
    if (!sido) return;
    if (sigunguIdx == null) onApply(sido.centroid, sido.regionName);
    else {
      const sg = sido.sigungus[sigunguIdx];
      onApply(sg.centroid, `${sido.regionName} ${sg.sigunguName}`);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.scrim} onPress={onClose}>
        <Pressable
          style={[styles.sheet, { paddingBottom: insets.bottom + spacing.md }]}
          onPress={(e) => e.stopPropagation()}
        >
          <View style={styles.header}>
            <Pressable style={styles.x} onPress={onClose} hitSlop={8}>
              <Icon name="close" size={22} />
            </Pressable>
            <Text style={styles.title}>지역 선택</Text>
          </View>

          {isError ? (
            <View style={styles.center}>
              <Text style={styles.errText}>지역 목록을 불러오지 못했어요</Text>
              <Pressable style={styles.retry} onPress={() => refetch()}>
                <Text style={styles.retryText}>다시 시도</Text>
              </Pressable>
            </View>
          ) : isLoading || !tree ? (
            <View style={styles.panes}>
              {[0, 1, 2, 3, 4].map((i) => (
                <Skeleton key={i} height={44} style={{ marginBottom: 6 }} />
              ))}
            </View>
          ) : (
            <View style={styles.panes}>
              <ScrollView style={styles.left} showsVerticalScrollIndicator={false}>
                {tree.map((r, i) => (
                  <Pressable
                    key={r.regionCode}
                    style={[styles.sidoRow, i === sidoIdx && styles.sidoActive]}
                    onPress={() => {
                      setSidoIdx(i);
                      setSigunguIdx(null);
                    }}
                  >
                    <Text style={[styles.sidoText, i === sidoIdx && styles.sidoTextActive]}>
                      {r.regionName}
                    </Text>
                  </Pressable>
                ))}
              </ScrollView>
              <ScrollView style={styles.right} showsVerticalScrollIndicator={false}>
                <Pressable style={styles.sgRow} onPress={() => setSigunguIdx(null)}>
                  <Text style={[styles.sgText, sigunguIdx == null && styles.sgActive]}>
                    {sido?.regionName} 전체
                  </Text>
                </Pressable>
                {sido?.sigungus.map((sg, i) => (
                  <Pressable
                    key={sg.sigunguCode}
                    style={styles.sgRow}
                    onPress={() => setSigunguIdx(i)}
                  >
                    <Text style={[styles.sgText, sigunguIdx === i && styles.sgActive]}>
                      {sg.sigunguName}
                    </Text>
                  </Pressable>
                ))}
              </ScrollView>
            </View>
          )}

          <Pressable style={styles.cta} onPress={apply} disabled={!tree}>
            <Text style={styles.ctaText}>검색</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: { flex: 1, justifyContent: "flex-end", backgroundColor: colors.scrim },
  sheet: {
    height: "62%",
    backgroundColor: colors.bg,
    borderTopLeftRadius: radii.xl,
    borderTopRightRadius: radii.xl,
  },
  header: {
    height: 52,
    alignItems: "center",
    justifyContent: "center",
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  x: {
    position: "absolute",
    left: 8,
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  title: { fontSize: 17, fontWeight: "700", color: colors.ink },
  panes: { flex: 1, flexDirection: "row" },
  left: { width: "34%", backgroundColor: colors.inset },
  right: { flex: 1 },
  sidoRow: { paddingVertical: 14, paddingHorizontal: spacing.md },
  sidoActive: { backgroundColor: colors.bg },
  sidoText: { fontSize: 14.5, color: colors.sec },
  sidoTextActive: { color: colors.ink, fontWeight: "700" },
  sgRow: { paddingVertical: 14, paddingHorizontal: spacing.lg },
  sgText: { fontSize: 15, color: colors.sec },
  sgActive: { color: colors.ink, fontWeight: "700" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  errText: { color: colors.sec, fontSize: 14 },
  retry: {
    paddingHorizontal: 18,
    height: 38,
    borderRadius: radii.pill,
    backgroundColor: colors.fill,
    alignItems: "center",
    justifyContent: "center",
  },
  retryText: { fontSize: 13.5, fontWeight: "700", color: colors.ink },
  cta: {
    height: 54,
    margin: spacing.lg,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  ctaText: { fontSize: 16, fontWeight: "700", color: colors.onImage },
});
