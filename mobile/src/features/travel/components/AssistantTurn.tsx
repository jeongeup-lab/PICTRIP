import { useCallback, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import { RichAnswerText } from "@/features/travel/components/RichAnswerText";
import { SourcesSheet, KIND_ICONS } from "@/features/travel/components/SourcesSheet";
import { ConditionRow } from "@/features/travel/components/ConditionRow";
import { SpotCarousel } from "@/features/travel/components/SpotCarousel";
import { StepSpinner } from "@/features/travel/components/StepSpinner";
import { agentErrorMessageForCode } from "@/features/travel/lib/agent-errors";
import { coordsOf } from "@/features/travel/lib/distance";
import { bounds, center, pinsFrom, placed } from "@/features/travel/lib/spot-geo";
import type { RefinePatch, TravelSpot } from "@/features/travel/api";
import type { ChatTurn } from "@/features/travel/stores/chat-store";
import type { LatLng } from "@/features/map/lib/geo";
import { colors, radii, spacing } from "@/constants/theme";

export const FAIL_TITLE = "답변을 못 받았어요";
export const RETRY_LABEL = "다시 시도";
export const SOURCES_LABEL = "소스";
export const THINKING_LABEL = "답변을 준비하는 중";

const MAP_PAD = 36;

interface Props {
  turn: ChatTurn;
  latest: boolean;
  origin: LatLng | null;
  onRetry: () => void;
  onDetail: (spot: TravelSpot) => void;
  onSaveToggle: (saved: boolean) => void;
  onNotice: (message: string) => void;
  onFocusSpot: (contentId: string | null) => void;
  onRefine: (patch: RefinePatch) => void;
}

function StepRow({ label, badge, done }: { label: string; badge: string | null; done: boolean }) {
  return (
    <View testID="travel-turn-step" style={styles.step}>
      {done ? (
        <Icon name="check" size={13} color={colors.sec} strokeWidth={2.2} />
      ) : (
        <StepSpinner />
      )}
      <Text style={styles.stepText} numberOfLines={1}>
        {label}
      </Text>
      {badge ? <Text style={styles.stepBadge}>{badge}</Text> : null}
    </View>
  );
}

export function AssistantTurn({
  turn,
  latest,
  origin,
  onRetry,
  onDetail,
  onSaveToggle,
  onNotice,
  onFocusSpot,
  onRefine,
}: Props) {
  const [focusedAt, setFocusedAt] = useState(0);
  const [scrollToAt, setScrollToAt] = useState<number | null>(null);
  const [sourcesOpen, setSourcesOpen] = useState(false);

  const mapSpots = useMemo(() => placed(turn.spots), [turn.spots]);
  const pins = useMemo(() => pinsFrom(mapSpots), [mapSpots]);
  const visibleSources = turn.sources.filter((source) => source.kind === "naver_blog");
  const fit = useMemo(() => {
    const box = bounds(mapSpots);
    if (!box) return null;
    return { ...box, pad: { top: MAP_PAD, right: MAP_PAD, bottom: MAP_PAD, left: MAP_PAD } };
  }, [mapSpots]);

  const focused = turn.spots[focusedAt] ?? null;
  const mapCenter = focused ? (coordsOf(focused) ?? center(mapSpots)) : center(mapSpots);

  const focusSpotAt = useCallback(
    (index: number, scroll: boolean) => {
      setFocusedAt(index);
      setScrollToAt(scroll ? index : null);
      if (latest) onFocusSpot(turn.spots[index]?.contentId ?? null);
    },
    [latest, onFocusSpot, turn.spots],
  );

  const onPinTap = useCallback(
    (contentId: string) => {
      const at = turn.spots.findIndex((spot) => spot.contentId === contentId);
      if (at < 0) return;
      focusSpotAt(at, true);
    },
    [turn.spots, focusSpotAt],
  );

  const streaming = turn.status === "streaming";
  const showMap = latest && pins.length > 0;

  return (
    <View style={styles.root}>
      {turn.steps.length > 0 ? (
        <View style={styles.steps}>
          {turn.steps.map((step) => (
            <StepRow
              key={step.index}
              label={step.label}
              badge={step.badge}
              done={step.status === "done"}
            />
          ))}
        </View>
      ) : streaming ? (
        <StepRow label={THINKING_LABEL} badge={null} done={false} />
      ) : null}

      {turn.text.length > 0 ? (
        <View style={styles.copy}>
          <RichAnswerText
            text={turn.text}
            spotCount={turn.spots.length}
            onCitePress={(number) => focusSpotAt(number - 1, true)}
          />
        </View>
      ) : null}

      <ConditionRow applied={turn.applied} refinements={turn.refinements} onRefine={onRefine} />

      {turn.spots.length > 0 ? (
        <View testID="travel-carousel-slot" style={styles.carouselSlot}>
          <SpotCarousel
            spots={turn.spots}
            tagBasis={turn.tagBasis}
            focusedIndex={focusedAt}
            scrollToIndex={scrollToAt}
            origin={origin}
            onFocusChange={(index) => focusSpotAt(index, false)}
            onDetail={onDetail}
            onSaveToggle={onSaveToggle}
            onMetricPress={onNotice}
          />
        </View>
      ) : null}

      {showMap ? (
        <View testID="travel-turn-map" style={styles.mapCard}>
          <KakaoWebMap
            center={mapCenter}
            fit={fit}
            pins={pins}
            anchorId={focused?.contentId ?? null}
            userLocation={origin}
            onPinTap={onPinTap}
          />
        </View>
      ) : null}

      {visibleSources.length > 0 ? (
        <Pressable
          testID="travel-sources"
          accessibilityRole="button"
          accessibilityLabel={`${SOURCES_LABEL} ${visibleSources.length}개 보기`}
          style={({ pressed }) => [styles.sourcesRow, pressed && styles.pressed]}
          onPress={() => setSourcesOpen(true)}
        >
          <View style={styles.faviconStack}>
            {visibleSources.slice(0, 3).map((source, index) => (
              <View
                key={`${index}-${source.title}`}
                style={[styles.favicon, index > 0 && styles.faviconOverlap]}
              >
                <Icon
                  name={KIND_ICONS[source.kind] ?? "globe"}
                  size={11}
                  color={colors.sec}
                  strokeWidth={1.9}
                />
              </View>
            ))}
          </View>
          <Text style={styles.sourcesText}>
            {SOURCES_LABEL} {visibleSources.length}
          </Text>
        </Pressable>
      ) : null}

      {turn.status === "error" ? (
        <View style={styles.failed}>
          <Text style={styles.failTitle}>{FAIL_TITLE}</Text>
          <Text style={styles.failReason}>{agentErrorMessageForCode(turn.errorCode)}</Text>
          <View style={styles.retryRow}>
            <Pressable
              testID="travel-retry"
              accessibilityRole="button"
              style={({ pressed }) => [styles.retry, pressed && styles.pressed]}
              onPress={onRetry}
            >
              <Text style={styles.retryText}>{RETRY_LABEL}</Text>
            </Pressable>
          </View>
        </View>
      ) : null}

      <SourcesSheet
        visible={sourcesOpen}
        items={visibleSources}
        onClose={() => setSourcesOpen(false)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { gap: spacing.sm },
  steps: { gap: 7 },
  step: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: spacing.md,
  },
  stepText: { flexShrink: 1, fontSize: 12.5, letterSpacing: -0.2, color: colors.sec },
  stepBadge: { fontSize: 11.5, fontWeight: "700", letterSpacing: -0.2, color: colors.ter },
  copy: { paddingHorizontal: spacing.md },
  carouselSlot: { marginTop: 2 },
  mapCard: {
    height: 190,
    marginHorizontal: spacing.md,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    overflow: "hidden",
  },
  sourcesRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    alignSelf: "flex-start",
    marginHorizontal: spacing.md,
    height: 30,
    paddingHorizontal: 11,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.fill,
  },
  faviconStack: { flexDirection: "row", alignItems: "center" },
  favicon: {
    width: 20,
    height: 20,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.inset,
  },
  faviconOverlap: { marginLeft: -7 },
  sourcesText: { fontSize: 12, fontWeight: "700", letterSpacing: -0.2, color: colors.sec },
  failed: {
    marginHorizontal: spacing.md,
    paddingLeft: 11,
    borderLeftWidth: 3,
    borderLeftColor: colors.accent,
  },
  failTitle: { fontSize: 13.5, fontWeight: "700", letterSpacing: -0.3, color: colors.accentText },
  failReason: {
    marginTop: 5,
    fontSize: 13,
    fontWeight: "600",
    lineHeight: 20,
    letterSpacing: -0.2,
    color: colors.sec,
  },
  retryRow: { flexDirection: "row", justifyContent: "flex-end", marginTop: 12 },
  retry: {
    height: 34,
    paddingHorizontal: 18,
    borderRadius: radii.lg,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  retryText: { fontSize: 13, fontWeight: "700", color: colors.onImage },
  pressed: { opacity: 0.7 },
});
