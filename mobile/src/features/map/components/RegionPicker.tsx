import { useEffect, useState } from "react";
import { Modal, View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Icon } from "@/components/Icon";
import { REGIONS } from "@/constants/regions";
import type { Centroid } from "@/lib/api-types";
import { colors, radii } from "@/constants/theme";

interface Props {
  visible: boolean;
  onClose: () => void;
  onApply: (centroid: Centroid, regionName: string) => void;
}

export function RegionPicker({ visible, onClose, onApply }: Props) {
  const insets = useSafeAreaInsets();
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

  const sido = REGIONS[sidoIdx];

  const apply = () => {
    if (sigunguIdx == null) onApply(sido.centroid, sido.regionName);
    else {
      const sg = sido.sigungus[sigunguIdx];
      onApply(sg.centroid, `${sido.regionName} ${sg.sigunguName}`);
    }
    onClose();
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.scrim} onPress={onClose}>
        <Pressable
          style={[styles.sheet, { paddingBottom: insets.bottom }]}
          onPress={(e) => e.stopPropagation()}
        >
          <View style={styles.header}>
            <Pressable style={styles.x} onPress={onClose} hitSlop={8}>
              <Icon name="close" size={24} color={colors.ter} />
            </Pressable>
            <Text style={styles.title}>지역 선택</Text>
          </View>

          <View style={styles.panes}>
            <ScrollView style={styles.left} showsVerticalScrollIndicator={false}>
              {REGIONS.map((r, i) => {
                const active = i === sidoIdx;
                return (
                  <Pressable
                    key={r.regionName}
                    style={styles.sidoRow}
                    onPress={() => {
                      setSidoIdx(i);
                      setSigunguIdx(null);
                    }}
                  >
                    <Text style={[styles.sidoText, active && styles.sidoTextActive]}>
                      {r.regionName}
                    </Text>
                    {active && <Icon name="chevron-right" size={17} color={colors.ink} />}
                  </Pressable>
                );
              })}
            </ScrollView>

            <ScrollView style={styles.right} showsVerticalScrollIndicator={false}>
              <Pressable style={styles.areaHead} onPress={() => setSigunguIdx(null)}>
                <Text style={styles.areaHeadText}>{sido.regionName} 전체</Text>
              </Pressable>
              {sido.sigungus.map((sg, i) => (
                <Pressable
                  key={sg.sigunguName}
                  style={styles.areaRow}
                  onPress={() => setSigunguIdx(i)}
                >
                  <Text style={[styles.areaText, sigunguIdx === i && styles.areaActive]}>
                    {sg.sigunguName}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
          </View>

          <View style={styles.ctaWrap}>
            <Pressable style={styles.cta} onPress={apply}>
              <Text style={styles.ctaText}>검색</Text>
            </Pressable>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const HAIR = "rgba(112,115,124,0.14)";

const styles = StyleSheet.create({
  scrim: { flex: 1, justifyContent: "flex-end", backgroundColor: colors.scrim },
  sheet: {
    height: "62%",
    backgroundColor: colors.bg,
    borderTopLeftRadius: radii.xl + 2,
    borderTopRightRadius: radii.xl + 2,
    overflow: "hidden",
  },
  header: {
    height: 62,
    alignItems: "center",
    justifyContent: "center",
    borderBottomWidth: 1,
    borderBottomColor: HAIR,
  },
  x: {
    position: "absolute",
    left: 8,
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  title: { fontSize: 18, fontWeight: "800", color: colors.ink },

  panes: { flex: 1, flexDirection: "row", minHeight: 0 },

  left: {
    width: "33%",
    backgroundColor: colors.inset,
    borderRightWidth: 1,
    borderRightColor: HAIR,
  },
  sidoRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 19,
    paddingHorizontal: 20,
  },
  sidoText: { fontSize: 17, fontWeight: "600", color: colors.ter },
  sidoTextActive: { color: colors.ink, fontWeight: "800" },

  right: { flex: 1, backgroundColor: colors.bg },
  areaHead: { paddingVertical: 19, paddingHorizontal: 22 },
  areaHeadText: { fontSize: 18, fontWeight: "800", color: colors.ink },
  areaRow: {
    paddingVertical: 18,
    paddingHorizontal: 22,
    borderTopWidth: 1,
    borderTopColor: HAIR,
  },
  areaText: { fontSize: 16, fontWeight: "500", color: colors.ter },
  areaActive: { color: colors.ink, fontWeight: "800" },

  ctaWrap: { paddingHorizontal: 18, paddingTop: 12, paddingBottom: 14 },
  cta: {
    height: 56,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  ctaText: { fontSize: 17, fontWeight: "800", color: colors.onImage },
});
