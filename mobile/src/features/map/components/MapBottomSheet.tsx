import { useEffect, useMemo, type ReactNode } from "react";
import { Animated, Dimensions, PanResponder, View, StyleSheet } from "react-native";
import { colors, radii, spacing } from "@/constants/theme";

type Snap = "peek" | "half" | "full";

interface Props {
  snap: Snap;
  onSnapChange: (s: Snap) => void;
  headerExtra?: ReactNode;
  children: ReactNode;
  onTranslate?: (v: Animated.Value) => void;
}

export const H = Dimensions.get("window").height;

// Collapsed ("peek") reveal budget — how many px of the sheet stay on-screen so
// the user still sees the drag handle + category chips + exactly ONE NearbyCard
// sitting above the tab bar. Derived from the actual component heights, NOT a
// screen ratio, so one card is always visible regardless of device height.
const HANDLE_ZONE_PX = 30; // handleZone: paddingTop 10 + grabber 4 + margin 10 + paddingBottom 6
const CHIPS_PX = 46; // CategoryChips: chip 34 + paddingVertical 6+6
const CARD_PX = 112; // NearbyCard: image 92 + paddingVertical 10+10
const TAB_BAR_PX = 83; // iOS tab content 49 + typical safe-area inset ~34 (card must clear it)
const PEEK_MARGIN_PX = 12;
export const PEEK_VISIBLE_PX = HANDLE_ZONE_PX + CHIPS_PX + CARD_PX + TAB_BAR_PX + PEEK_MARGIN_PX;

// translateY from the top of the sheet container; smaller = taller sheet.
// Exported so the map screen can anchor the search pill + recenter FAB to the
// sheet's top edge (see map.tsx fallback initial value).
export const SHEET_SNAP_Y: Record<Snap, number> = {
  peek: H - PEEK_VISIBLE_PX,
  half: H * 0.42,
  full: H * 0.08,
};
const Y = SHEET_SNAP_Y;

export function MapBottomSheet({ snap, onSnapChange, headerExtra, children, onTranslate }: Props) {
  // eslint-disable-next-line react-hooks/exhaustive-deps -- stable value: init once, never re-create.
  const y = useMemo(() => new Animated.Value(Y[snap]), []);

  useEffect(() => {
    onTranslate?.(y);
  }, [y, onTranslate]);

  useEffect(() => {
    // JS driver (not native): the map screen anchors the search pill + recenter
    // FAB to this value via Animated.subtract. A native-driven spring never
    // updates the JS value, so those JS-side followers would freeze mid-snap.
    // JS-driving keeps the shared value updating every frame for both.
    Animated.spring(y, { toValue: Y[snap], useNativeDriver: false, bounciness: 2 }).start();
  }, [snap, y]);

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
    [snap, y, onSnapChange],
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
    borderTopLeftRadius: radii.xl,
    borderTopRightRadius: radii.xl,
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
