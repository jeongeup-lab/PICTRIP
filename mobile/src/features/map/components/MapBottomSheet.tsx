import { useEffect, useMemo, type ReactNode } from "react";
import { Animated, Dimensions, PanResponder, View, StyleSheet } from "react-native";
import { sheetSnapY, type SheetSnap } from "@/features/map/lib/sheet-snap";
import { colors, spacing } from "@/constants/theme";

type Snap = SheetSnap;

interface Props {
  snap: Snap;
  onSnapChange: (s: Snap) => void;
  headerExtra?: ReactNode;
  children: ReactNode;
  onTranslate?: (v: Animated.Value) => void;
  snapY?: Record<Snap, number>;
}

export const H = Dimensions.get("window").height;

export const SHEET_SNAP_Y: Record<Snap, number> = sheetSnapY(H);

export function MapBottomSheet({
  snap,
  onSnapChange,
  headerExtra,
  children,
  onTranslate,
  snapY = SHEET_SNAP_Y,
}: Props) {
  const Y = snapY;
  // eslint-disable-next-line react-hooks/exhaustive-deps -- stable value: init once, never re-create.
  const y = useMemo(() => new Animated.Value(Y[snap]), []);

  useEffect(() => {
    onTranslate?.(y);
  }, [y, onTranslate]);

  useEffect(() => {
    Animated.spring(y, { toValue: Y[snap], useNativeDriver: false, bounciness: 2 }).start();
  }, [snap, y, Y]);

  const pan = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_e, g) => Math.abs(g.dy) > 6,
        onPanResponderMove: (_e, g) => {
          const next = Y[snap] + g.dy;
          y.setValue(Math.max(Y.full, Math.min(Y.peek, next)));
        },
        onPanResponderRelease: (_e, g) => {
          const landing = Y[snap] + g.dy;
          const nearest = (["full", "half", "peek"] as Snap[]).reduce((best, s) =>
            Math.abs(Y[s] - landing) < Math.abs(Y[best] - landing) ? s : best,
          );
          onSnapChange(nearest);
          Animated.spring(y, {
            toValue: Y[nearest],
            useNativeDriver: false,
            bounciness: 2,
          }).start();
        },
      }),
    [snap, y, onSnapChange, Y],
  );

  return (
    <Animated.View style={[styles.sheet, { transform: [{ translateY: y }] }]}>
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
    height: H,
    backgroundColor: colors.bg,
    borderTopLeftRadius: 14,
    borderTopRightRadius: 14,
    shadowColor: "#100E12",
    shadowOpacity: 0.16,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: -4 },
    elevation: 12,
  },
  handleZone: { paddingTop: spacing.sm, paddingBottom: spacing.xs },
  grabber: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.line,
    marginBottom: spacing.sm,
  },
  body: { flex: 1 },
});
