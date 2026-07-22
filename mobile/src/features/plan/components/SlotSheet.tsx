import { useState } from "react";
import { Modal, Pressable, ScrollView, View, Text, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon, type IconName } from "@/components/Icon";
import type { ResolvedSpot, ScheduleSlot } from "@/features/plan/api";
import { placeName, shortRegion } from "@/features/plan/lib/plan-format";
import { openKakaoRoute, openNaverRoute } from "@/features/plan/lib/map-links";
import { useAlternatives } from "@/features/plan/queries";
import { PlanLoading } from "@/features/plan/components/PlanLoading";
import { colors, radii, spacing } from "@/constants/theme";

interface Props {
  planId: string;
  slot: ScheduleSlot;
  day: number;
  slotIndex: number;
  onClose: () => void;
  onRemove: () => void;
  onReplace: (spot: ResolvedSpot) => void;
}

function ActionRow({
  icon,
  label,
  tone,
  testID,
  onPress,
}: {
  icon?: IconName;
  label: string;
  tone?: "danger" | "quiet";
  testID?: string;
  onPress: () => void;
}) {
  const color = tone === "danger" ? colors.danger : tone === "quiet" ? colors.ter : colors.ink;
  return (
    <Pressable
      testID={testID}
      style={({ pressed }) => [
        styles.action,
        tone === "quiet" && styles.actionQuiet,
        pressed && styles.pressed,
      ]}
      onPress={onPress}
    >
      {icon ? (
        <Icon name={icon} size={21} color={tone === "danger" ? colors.danger : colors.sec} />
      ) : null}
      <Text style={[styles.actionText, { color }]}>{label}</Text>
    </Pressable>
  );
}

export function SlotSheet({ planId, slot, day, slotIndex, onClose, onRemove, onReplace }: Props) {
  const insets = useSafeAreaInsets();
  const [swapping, setSwapping] = useState(false);
  const alternatives = useAlternatives(planId, swapping ? { day, slot: slotIndex } : null);

  const spot = slot.place.spot;
  const name = placeName(slot.place);
  const target = { title: name, lat: spot?.lat ?? null, lng: spot?.lng ?? null };

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.scrim} onPress={onClose}>
        <Pressable
          style={[styles.sheet, { paddingBottom: insets.bottom + spacing.xl }]}
          onPress={(e) => e.stopPropagation()}
        >
          <View style={styles.grabber} />

          {swapping ? (
            <SwapBody
              name={name}
              loading={alternatives.isLoading}
              failed={alternatives.isError}
              alternatives={alternatives.data ?? []}
              onPick={onReplace}
            />
          ) : (
            <>
              <Text style={styles.title}>{name}</Text>
              {spot?.address ? <Text style={styles.sub}>{spot.address}</Text> : null}

              <ActionRow
                icon="map-pin"
                label="카카오맵 길찾기"
                testID="slot-kakao"
                onPress={() => openKakaoRoute(target)}
              />
              <ActionRow
                icon="map-pin"
                label="네이버지도에서 보기"
                testID="slot-naver"
                onPress={() => openNaverRoute(target)}
              />
              <ActionRow
                icon="swap"
                label="다른 곳으로 교체"
                testID="slot-swap"
                onPress={() => setSwapping(true)}
              />
              <ActionRow
                icon="trash"
                label="일정에서 삭제"
                tone="danger"
                testID="slot-remove"
                onPress={onRemove}
              />
              <ActionRow label="닫기" tone="quiet" onPress={onClose} />
            </>
          )}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function SwapBody({
  name,
  loading,
  failed,
  alternatives,
  onPick,
}: {
  name: string;
  loading: boolean;
  failed: boolean;
  alternatives: ResolvedSpot[];
  onPick: (spot: ResolvedSpot) => void;
}) {
  if (loading) return <PlanLoading title="주변 대안을 찾고 있어요" />;

  if (failed || alternatives.length === 0) {
    return (
      <View style={styles.emptySwap}>
        <Text style={styles.sub}>주변에서 대안을 찾지 못했어요</Text>
      </View>
    );
  }

  return (
    <>
      <Text style={styles.title}>여기 대신 갈 만한 곳</Text>
      <Text style={styles.sub}>{name} 근처</Text>
      <ScrollView style={styles.altList}>
        {alternatives.map((alt) => (
          <Pressable
            key={alt.contentId ?? alt.title}
            testID={`alt-${alt.contentId ?? alt.title}`}
            style={({ pressed }) => [styles.altRow, pressed && styles.pressed]}
            onPress={() => onPick(alt)}
          >
            <RemoteImage uri={alt.imageUrl} style={styles.altImage} radius={radii.md} />
            <View style={styles.altBody}>
              <Text style={styles.altTitle} numberOfLines={1}>
                {alt.title}
              </Text>
              <Text style={styles.altMeta} numberOfLines={1}>
                {[alt.category, shortRegion(alt.address)].filter(Boolean).join(" · ")}
              </Text>
            </View>
            <Text style={styles.altSwap}>교체</Text>
          </Pressable>
        ))}
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  scrim: { flex: 1, justifyContent: "flex-end", backgroundColor: colors.scrim },
  sheet: {
    maxHeight: "72%",
    backgroundColor: colors.bg,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingTop: spacing.xs,
    paddingHorizontal: spacing.lg,
  },
  grabber: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.line,
    marginVertical: spacing.sm,
  },
  title: { fontSize: 18, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  sub: { marginTop: 4, fontSize: 12.5, color: colors.ter },
  pressed: { backgroundColor: colors.fill },
  action: {
    flexDirection: "row",
    alignItems: "center",
    gap: 13,
    paddingVertical: 16,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  actionQuiet: { justifyContent: "center" },
  actionText: { fontSize: 15.5, fontWeight: "600", letterSpacing: -0.2 },
  emptySwap: { paddingVertical: spacing.xl, alignItems: "center" },
  altList: { marginTop: spacing.xs },
  altRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  altImage: { width: 56, height: 56 },
  altBody: { flex: 1, gap: 3 },
  altTitle: { fontSize: 15, fontWeight: "700", letterSpacing: -0.2, color: colors.ink },
  altMeta: { fontSize: 12.5, color: colors.ter },
  altSwap: { fontSize: 12.5, fontWeight: "700", color: colors.accentText },
});
