import { ActivityIndicator, Animated, Pressable, StyleSheet, Text, View } from "react-native";
import type { PanResponderInstance } from "react-native";
import { Icon } from "@/components/Icon";
import { RemoteImage } from "@/components/RemoteImage";
import type { HomeSpotCard } from "@/features/home/api";
import { colors, spacing } from "@/constants/theme";
import { styles } from "@/features/home/components/taste-picker-styles";
import {
  TastePickerCompletion,
  TastePickerScrim,
  TastePickerState,
} from "@/features/home/components/TastePickerStates";

const SWIPE_THRESHOLD = 110;
const MAX_TILT_DEG = 9;

interface Props {
  readonly cards: readonly HomeSpotCard[];
  readonly activeCard: HomeSpotCard | undefined;
  readonly upcomingCard: HomeSpotCard | undefined;
  readonly reviewedCount: number;
  readonly enoughSaves: boolean;
  readonly isLoading: boolean;
  readonly unavailable: boolean;
  readonly done: boolean;
  readonly busy: boolean;
  readonly error: "save" | "undo" | null;
  readonly hasHistory: boolean;
  readonly pan: Animated.ValueXY;
  readonly responder: PanResponderInstance | null;
  readonly width: number;
  readonly height: number;
  readonly topInset: number;
  readonly bottomInset: number;
  readonly onClose: () => void;
  readonly onUndo: () => void;
  readonly onSave: () => void;
  readonly onSkip: () => void;
}

export function TastePickerView(props: Props) {
  if (props.isLoading) return <TastePickerState text="취향 카드를 준비하고 있어요" loading />;
  if (props.unavailable)
    return <TastePickerState text="지금은 보여줄 카드가 없어요" onClose={props.onClose} />;
  const cardWidth = props.width - spacing.lg * 2;
  const cardHeight = Math.min(Math.round(cardWidth * 1.25), props.height - props.topInset - 300);
  const rotate = props.pan.x.interpolate({
    inputRange: [-props.width, 0, props.width],
    outputRange: [`-${MAX_TILT_DEG}deg`, "0deg", `${MAX_TILT_DEG}deg`],
  });
  const keepOpacity = props.pan.x.interpolate({
    inputRange: [0, SWIPE_THRESHOLD],
    outputRange: [0, 1],
    extrapolate: "clamp",
  });
  const skipOpacity = props.pan.x.interpolate({
    inputRange: [-SWIPE_THRESHOLD, 0],
    outputRange: [1, 0],
    extrapolate: "clamp",
  });
  const nextScale = props.pan.x.interpolate({
    inputRange: [-SWIPE_THRESHOLD, 0, SWIPE_THRESHOLD],
    outputRange: [1, 0.94, 1],
    extrapolate: "clamp",
  });
  return (
    <View style={[styles.root, { paddingTop: props.topInset + 12 }]}>
      <View style={styles.topRow}>
        <Text
          testID="taste-progress"
          style={styles.progress}
        >{`${props.reviewedCount}/${props.cards.length} 검토`}</Text>
        <Pressable
          testID="taste-close"
          accessibilityLabel="취향 카드 닫기"
          onPress={props.onClose}
          style={styles.iconButton}
        >
          <Icon name="close" size={20} color={colors.onImage} />
        </Pressable>
      </View>
      <View style={styles.segments}>
        {props.cards.map((card, index) => (
          <View key={card.contentId} style={styles.segTrack}>
            <View
              style={[
                styles.segFill,
                {
                  opacity:
                    index < props.reviewedCount ? 1 : index === props.reviewedCount ? 0.6 : 0.25,
                },
              ]}
            />
          </View>
        ))}
      </View>
      {props.done ? (
        <TastePickerCompletion enoughSaves={props.enoughSaves} onClose={props.onClose} />
      ) : props.activeCard ? (
        <>
          <View style={styles.cardWrap}>
            {props.upcomingCard ? (
              <Animated.View
                pointerEvents="none"
                style={[
                  styles.card,
                  styles.stacked,
                  { width: cardWidth, height: cardHeight, transform: [{ scale: nextScale }] },
                ]}
              >
                <RemoteImage uri={props.upcomingCard.imageUrl} style={StyleSheet.absoluteFill} />
              </Animated.View>
            ) : null}
            <Animated.View
              testID="taste-card"
              {...props.responder?.panHandlers}
              style={[
                styles.card,
                {
                  width: cardWidth,
                  height: cardHeight,
                  transform: [{ translateX: props.pan.x }, { translateY: props.pan.y }, { rotate }],
                },
              ]}
            >
              <RemoteImage uri={props.activeCard.imageUrl} style={StyleSheet.absoluteFill} />
              <TastePickerScrim />
              <Animated.View
                pointerEvents="none"
                style={[styles.stamp, styles.stampKeep, { opacity: keepOpacity }]}
              >
                <Text style={[styles.stampText, styles.stampKeepText]}>저장</Text>
              </Animated.View>
              <Animated.View
                pointerEvents="none"
                style={[styles.stamp, styles.stampSkip, { opacity: skipOpacity }]}
              >
                <Text style={styles.stampText}>넘기기</Text>
              </Animated.View>
              <View style={styles.cardMeta}>
                <Text style={styles.cardTitle} numberOfLines={2}>
                  {props.activeCard.title}
                </Text>
                <Text style={styles.cardRegion} numberOfLines={1}>
                  {[props.activeCard.category, props.activeCard.regionLabel]
                    .filter(Boolean)
                    .join(" · ")}
                </Text>
              </View>
            </Animated.View>
          </View>
          <Text style={styles.hint}>오른쪽으로 밀면 저장, 왼쪽으로 밀면 넘겨요</Text>
        </>
      ) : null}
      {props.error ? (
        <Text testID="taste-error" style={styles.error}>
          {props.error === "save"
            ? "저장하지 못했어요. 연결을 확인하고 다시 시도해 주세요."
            : "되돌리지 못했어요. 다시 시도해 주세요."}
        </Text>
      ) : null}
      <Pressable
        testID="taste-undo"
        accessibilityLabel="방금 선택 되돌리기"
        disabled={!props.hasHistory || props.busy}
        onPress={props.onUndo}
        style={[styles.undo, (!props.hasHistory || props.busy) && styles.dimmed]}
      >
        <Text style={styles.undoText}>방금 선택 되돌리기</Text>
      </Pressable>
      {!props.done ? (
        <View style={[styles.actions, { paddingBottom: props.bottomInset + spacing.lg }]}>
          <Pressable
            testID="taste-skip"
            accessibilityLabel="넘기기"
            disabled={props.busy}
            onPress={props.onSkip}
            style={[styles.skip, props.busy && styles.dimmed]}
          >
            <Icon name="close" size={22} color={colors.sec} />
            <Text style={styles.skipText}>넘기기</Text>
          </Pressable>
          <Pressable
            testID="taste-keep"
            accessibilityLabel="저장"
            disabled={props.busy}
            onPress={props.onSave}
            style={[styles.keep, props.busy && styles.dimmed]}
          >
            {props.busy ? (
              <ActivityIndicator color={colors.onImage} />
            ) : (
              <>
                <Icon name="bookmark-fill" size={24} color={colors.onImage} />
                <Text style={styles.keepText}>저장</Text>
              </>
            )}
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}
