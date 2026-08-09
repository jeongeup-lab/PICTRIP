import { useEffect, useRef, useState, type ReactNode } from "react";
import { Animated, Easing, Pressable, StyleSheet, View, useWindowDimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, shadows } from "@/constants/theme";
import {
  SHEET_ANIM_MS,
  sheetBottomPx,
  sheetHeightPx,
  type SheetSnap,
} from "@/features/travel/lib/sheet-layout";

const SHEET_RADIUS = 22;

interface Props {
  snap: SheetSnap;
  keyboardPx: number;
  dockPx: number;
  onGrabberTap: () => void;
  children: ReactNode;
}

export function TravelSheet({ snap, keyboardPx, dockPx, onGrabberTap, children }: Props) {
  const { height: frameH } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const targetHeight = sheetHeightPx({
    snap,
    frameH,
    insetTop: insets.top,
    insetBottom: insets.bottom,
    keyboardPx,
    dockPx,
  });
  const targetBottom = sheetBottomPx({ keyboardPx });
  const [height] = useState(() => new Animated.Value(targetHeight));
  const [bottom] = useState(() => new Animated.Value(targetBottom));
  const settled = useRef({ height: targetHeight, bottom: targetBottom });

  useEffect(() => {
    if (settled.current.height === targetHeight && settled.current.bottom === targetBottom) {
      return;
    }
    settled.current = { height: targetHeight, bottom: targetBottom };
    Animated.parallel([
      Animated.timing(height, {
        toValue: targetHeight,
        duration: SHEET_ANIM_MS,
        easing: Easing.inOut(Easing.cubic),
        useNativeDriver: false,
      }),
      Animated.timing(bottom, {
        toValue: targetBottom,
        duration: SHEET_ANIM_MS,
        easing: Easing.inOut(Easing.cubic),
        useNativeDriver: false,
      }),
    ]).start();
  }, [height, bottom, targetHeight, targetBottom]);

  return (
    <Animated.View testID="travel-sheet" style={[sheetStyles.root, { height, bottom }]}>
      {snap !== "collapsed" && (
        <Pressable
          testID="travel-sheet-grabber"
          accessibilityRole="button"
          accessibilityLabel="시트 크기 전환"
          onPress={onGrabberTap}
          style={sheetStyles.grabberZone}
        >
          <View style={sheetStyles.pill} />
        </Pressable>
      )}
      <View style={sheetStyles.body}>{children}</View>
    </Animated.View>
  );
}

export const sheetStyles = StyleSheet.create({
  root: {
    position: "absolute",
    left: 0,
    right: 0,
    backgroundColor: colors.inset,
    borderTopLeftRadius: SHEET_RADIUS,
    borderTopRightRadius: SHEET_RADIUS,
    borderTopWidth: 1,
    borderTopColor: colors.glassBorder,
    ...shadows.sheet,
  },
  grabberZone: {
    height: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  pill: {
    width: 44,
    height: 5,
    borderRadius: 3,
    backgroundColor: colors.fillStrong,
  },
  body: {
    flex: 1,
    borderTopLeftRadius: SHEET_RADIUS,
    borderTopRightRadius: SHEET_RADIUS,
    overflow: "hidden",
  },
});
