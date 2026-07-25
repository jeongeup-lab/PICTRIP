import { useEffect, useMemo, useState } from "react";
import { Animated, Easing, Modal, Pressable, View, Text, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { Conditions } from "@/features/travel/api";
import {
  REGION_OPTIONS,
  WHEN_OPTIONS,
  WHO_OPTIONS,
  type ConditionOption,
} from "@/features/travel/lib/condition-labels";
import { colors, radii, spacing } from "@/constants/theme";

const SHEET_MS = 320;

interface Props {
  open: boolean;
  conditions: Conditions;
  onClose: () => void;
  onApply: (next: Conditions) => void;
}

function SegmentGroup<V extends string>({
  label,
  options,
  value,
  onSelect,
}: {
  label: string;
  options: readonly ConditionOption<V>[];
  value: V;
  onSelect: (v: V) => void;
}) {
  return (
    <View>
      <Text style={styles.groupLabel}>{label}</Text>
      <View style={styles.segments}>
        {options.map((option) => {
          const active = option.value === value;
          return (
            <Pressable
              key={option.value}
              testID={`condition-${option.value}`}
              style={[styles.segment, active && styles.segmentOn]}
              onPress={() => onSelect(option.value)}
            >
              <Text style={[styles.segmentText, active && styles.segmentTextOn]}>
                {option.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

export function ConditionSheet({ open, conditions, onClose, onApply }: Props) {
  const insets = useSafeAreaInsets();
  const slide = useMemo(() => new Animated.Value(0), []);
  const [draft, setDraft] = useState<Conditions>(conditions);
  const [wasOpen, setWasOpen] = useState(open);

  if (wasOpen !== open) {
    setWasOpen(open);
    if (open) setDraft(conditions);
  }

  useEffect(() => {
    Animated.timing(slide, {
      toValue: open ? 1 : 0,
      duration: SHEET_MS,
      easing: Easing.bezier(0.2, 0.8, 0.2, 1),
      useNativeDriver: true,
    }).start();
  }, [open, slide]);

  return (
    <Modal visible={open} transparent animationType="none" onRequestClose={onClose}>
      <Animated.View style={[styles.dim, { opacity: slide }]}>
        <Pressable testID="condition-dim" style={StyleSheet.absoluteFill} onPress={onClose} />
      </Animated.View>
      <Animated.View
        testID="condition-sheet"
        style={[
          styles.sheet,
          { paddingBottom: spacing.xxl + insets.bottom },
          {
            transform: [
              { translateY: slide.interpolate({ inputRange: [0, 1], outputRange: [600, 0] }) },
            ],
          },
        ]}
      >
        <View style={styles.handle} />
        <Text style={styles.title}>조건</Text>

        <SegmentGroup
          label="지역"
          options={REGION_OPTIONS}
          value={draft.region}
          onSelect={(region) => setDraft((d) => ({ ...d, region }))}
        />
        <SegmentGroup
          label="언제"
          options={WHEN_OPTIONS}
          value={draft.when}
          onSelect={(when) => setDraft((d) => ({ ...d, when }))}
        />
        <SegmentGroup
          label="누구와"
          options={WHO_OPTIONS}
          value={draft.who}
          onSelect={(who) => setDraft((d) => ({ ...d, who }))}
        />

        <Pressable testID="condition-apply" style={styles.apply} onPress={() => onApply(draft)}>
          <Text style={styles.applyText}>적용</Text>
        </Pressable>
      </Animated.View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  dim: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: colors.scrim,
  },
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: colors.bg,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingTop: 10,
    paddingHorizontal: spacing.xl,
  },
  handle: {
    width: 44,
    height: 5,
    borderRadius: 3,
    backgroundColor: colors.skeleton,
    alignSelf: "center",
    marginTop: 6,
    marginBottom: 18,
  },
  title: { fontSize: 17, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  groupLabel: {
    marginTop: 16,
    marginBottom: 9,
    fontSize: 12.5,
    fontWeight: "700",
    color: colors.ter,
  },
  segments: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  segment: {
    height: 34,
    paddingHorizontal: 16,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.line,
    justifyContent: "center",
    backgroundColor: colors.bg,
  },
  segmentOn: { backgroundColor: colors.ink, borderColor: colors.ink },
  segmentText: { fontSize: 13.5, fontWeight: "700", color: colors.sec },
  segmentTextOn: { color: colors.onImage },
  apply: {
    marginTop: 24,
    height: 52,
    borderRadius: radii.lg,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  applyText: { fontSize: 15.5, fontWeight: "700", letterSpacing: -0.3, color: colors.onImage },
});
