import { useMemo, useState, type ReactNode } from "react";
import { Animated, PanResponder, Pressable, Text, View, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import {
  SWIPE_ACTION_WIDTH,
  restOffset,
  shouldCaptureSwipe,
  swipeOffset,
  swipeOutcome,
} from "@/features/saved/lib/swipe";
import { colors } from "@/constants/theme";

interface Props {
  children: ReactNode;
  actionLabel: string;
  onAction: () => void;
  testID?: string;
}

export function SwipeRow({ children, actionLabel, onAction, testID }: Props) {
  const x = useMemo(() => new Animated.Value(0), []);
  const [open, setOpen] = useState(false);

  const pan = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_e, g) => shouldCaptureSwipe(g.dx, g.dy),
        onPanResponderMove: (_e, g) => x.setValue(swipeOffset(g.dx, open)),
        onPanResponderRelease: (_e, g) => {
          const outcome = swipeOutcome(swipeOffset(g.dx, open), g.vx);
          if (outcome === "delete") {
            setOpen(false);
            x.setValue(0);
            onAction();
            return;
          }
          setOpen(outcome === "open");
          Animated.spring(x, {
            toValue: restOffset(outcome),
            useNativeDriver: false,
            bounciness: 0,
          }).start();
        },
        onPanResponderTerminate: () => {
          setOpen(false);
          Animated.spring(x, { toValue: 0, useNativeDriver: false, bounciness: 0 }).start();
        },
      }),
    [x, open, onAction],
  );

  const runAction = () => {
    setOpen(false);
    x.setValue(0);
    onAction();
  };

  return (
    <View style={styles.wrap} testID={testID}>
      <Pressable
        accessibilityRole="button"
        style={styles.action}
        onPress={runAction}
        testID={testID ? `${testID}-action` : undefined}
      >
        <Icon name="heart-off" size={17} color={colors.onImage} strokeWidth={1.8} />
        <Text style={styles.actionText}>{actionLabel}</Text>
      </Pressable>
      <Animated.View style={[styles.face, { transform: [{ translateX: x }] }]} {...pan.panHandlers}>
        {children}
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { overflow: "hidden", backgroundColor: colors.accent },
  action: {
    position: "absolute",
    top: 0,
    bottom: 0,
    right: 0,
    width: SWIPE_ACTION_WIDTH,
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
  },
  actionText: { fontSize: 12.5, fontWeight: "800", color: colors.onImage },
  face: { backgroundColor: colors.bg },
});
