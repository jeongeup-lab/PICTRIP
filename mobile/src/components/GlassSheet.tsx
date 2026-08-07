import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Animated, Dimensions, PanResponder, View, StyleSheet } from "react-native";
import { nearestSnap, type SheetSnap } from "@/lib/sheet-snap";
import { colors, radii, shadows } from "@/constants/theme";

export const SCREEN_H = Dimensions.get("window").height;

const DRAG_THRESHOLD_PX = 6;

interface Props {
  snap: SheetSnap;
  snapY: Record<SheetSnap, number>;
  onSnapChange: (s: SheetSnap) => void;
  headerExtra?: ReactNode;
  children: ReactNode;
  onTranslate?: (v: Animated.Value) => void;
  testID?: string;
}

export function GlassSheet({
  snap,
  snapY,
  onSnapChange,
  headerExtra,
  children,
  onTranslate,
  testID,
}: Props) {
  const [y] = useState(() => new Animated.Value(snapY[snap]));

  useEffect(() => {
    onTranslate?.(y);
  }, [y, onTranslate]);

  useEffect(() => {
    Animated.spring(y, { toValue: snapY[snap], useNativeDriver: false, bounciness: 2 }).start();
  }, [snap, y, snapY]);

  const pan = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_e, g) => Math.abs(g.dy) > DRAG_THRESHOLD_PX,
        onPanResponderMove: (_e, g) => {
          const next = snapY[snap] + g.dy;
          y.setValue(Math.max(snapY.full, Math.min(snapY.peek, next)));
        },
        onPanResponderRelease: (_e, g) => {
          const landing = nearestSnap(snapY[snap] + g.dy, snapY);
          onSnapChange(landing);
          Animated.spring(y, {
            toValue: snapY[landing],
            useNativeDriver: false,
            bounciness: 2,
          }).start();
        },
      }),
    [snap, y, onSnapChange, snapY],
  );

  return (
    <Animated.View
      testID={testID}
      style={[styles.sheet, { transform: [{ translateY: y }] }]}
      accessibilityViewIsModal={false}
    >
      <View style={styles.handleZone} {...pan.panHandlers}>
        <View style={styles.grabber} />
        {headerExtra}
      </View>
      <View style={styles.body}>{children}</View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    top: 0,
    height: SCREEN_H,
    backgroundColor: colors.glassFill,
    borderTopWidth: 1,
    borderTopColor: colors.glassBorder,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    overflow: "hidden",
    ...shadows.sheet,
  },
  handleZone: { paddingTop: 9, paddingBottom: 4 },
  grabber: {
    alignSelf: "center",
    width: 38,
    height: 5,
    borderRadius: radii.pill,
    backgroundColor: "rgba(255,255,255,0.28)",
  },
  body: { flex: 1 },
});
