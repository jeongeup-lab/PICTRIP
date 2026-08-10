import { useEffect, useRef, useState, type ReactNode } from "react";
import { Animated, Easing, Pressable, StyleSheet, View, useWindowDimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Icon } from "@/components/Icon";
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
  onCollapse: () => void;
  children: ReactNode;
}

export function TravelSheet({
  snap,
  keyboardPx,
  dockPx,
  onGrabberTap,
  onCollapse,
  children,
}: Props) {
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
        <View style={sheetStyles.header}>
          <Pressable
            testID="travel-sheet-grabber"
            accessibilityRole="button"
            accessibilityLabel="시트 크기 전환"
            onPress={onGrabberTap}
            style={sheetStyles.grabberZone}
          >
            <View style={sheetStyles.pill} />
          </Pressable>
          <Pressable
            testID="travel-sheet-collapse"
            accessibilityRole="button"
            accessibilityLabel="시트 내리기"
            hitSlop={8}
            onPress={onCollapse}
            style={sheetStyles.collapse}
          >
            <Icon name="chevron-down" size={16} color={colors.ter} strokeWidth={2} />
          </Pressable>
        </View>
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
  header: {},
  grabberZone: {
    height: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  collapse: {
    position: "absolute",
    right: 14,
    top: 0,
    height: 20,
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
