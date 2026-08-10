import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Animated,
  Easing,
  Pressable,
  StyleSheet,
  View,
  useWindowDimensions,
  type GestureResponderEvent,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, shadows } from "@/constants/theme";
import {
  clampToSheet,
  settleSnap,
  SHEET_ANIM_MS,
  SHEET_HEADER_PX,
  sheetBottomPx,
  sheetHeightPx,
  snapHeights,
  type SheetSnap,
} from "@/features/travel/lib/sheet-layout";

const SHEET_RADIUS = 22;

interface Props {
  snap: SheetSnap;
  keyboardPx: number;
  dockPx: number;
  greeting: boolean;
  onGrabberTap: () => void;
  onSnapChange: (snap: SheetSnap) => void;
  children: ReactNode;
}

export function TravelSheet({
  snap,
  keyboardPx,
  dockPx,
  greeting,
  onGrabberTap,
  children,
  onSnapChange,
}: Props) {
  const { height: frameH } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const metrics = {
    frameH,
    insetTop: insets.top,
    insetBottom: insets.bottom,
    keyboardPx,
    dockPx,
    greeting,
  };
  const targetHeight = sheetHeightPx({ ...metrics, snap });
  const targetBottom = sheetBottomPx({ keyboardPx });
  const [height] = useState(() => new Animated.Value(targetHeight));
  const [bottom] = useState(() => new Animated.Value(targetBottom));
  const [dragging, setDragging] = useState(false);
  const settled = useRef({ height: targetHeight, bottom: targetBottom });
  const drag = useRef({ from: 0, startY: 0, lastY: 0, lastAt: 0 });

  const heights = snapHeights(metrics);

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

  const settleTo = (next: SheetSnap) => {
    settled.current = { ...settled.current, height: heights[next] };
    Animated.timing(height, {
      toValue: heights[next],
      duration: SHEET_ANIM_MS,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    }).start();
    if (next !== snap) onSnapChange(next);
  };

  const onDragStart = (event: GestureResponderEvent) => {
    const { pageY, timestamp } = event.nativeEvent;
    setDragging(true);
    drag.current = { from: settled.current.height, startY: pageY, lastY: pageY, lastAt: timestamp };
    height.stopAnimation((value: number) => {
      drag.current.from = value;
    });
  };

  const dragHeight = (event: GestureResponderEvent) =>
    clampToSheet(drag.current.from - (event.nativeEvent.pageY - drag.current.startY), heights);

  const onDragMove = (event: GestureResponderEvent) => {
    const { pageY, timestamp } = event.nativeEvent;
    height.setValue(dragHeight(event));
    if (timestamp !== drag.current.lastAt) {
      drag.current.lastY = pageY;
      drag.current.lastAt = timestamp;
    }
  };

  const onDragEnd = (event: GestureResponderEvent) => {
    const { pageY, timestamp } = event.nativeEvent;
    const elapsed = timestamp - drag.current.lastAt;
    setDragging(false);
    settleTo(
      settleSnap({
        heights,
        from: snap,
        height: dragHeight(event),
        velocityY: elapsed > 0 ? (pageY - drag.current.lastY) / elapsed : 0,
      }),
    );
  };

  return (
    <Animated.View testID="travel-sheet" style={[sheetStyles.root, { height, bottom }]}>
      <View
        testID="travel-sheet-header"
        style={sheetStyles.header}
        onStartShouldSetResponder={() => false}
        onMoveShouldSetResponder={() => true}
        onResponderTerminationRequest={() => false}
        onResponderGrant={onDragStart}
        onResponderMove={onDragMove}
        onResponderRelease={onDragEnd}
        onResponderTerminate={onDragEnd}
      >
        <Pressable
          testID="travel-sheet-grabber"
          accessibilityRole="button"
          accessibilityLabel="시트 크기 전환"
          onPress={onGrabberTap}
          style={sheetStyles.grabberZone}
        >
          <View style={sheetStyles.pill} />
        </Pressable>
      </View>
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
  header: { height: SHEET_HEADER_PX },
  grabberZone: {
    height: SHEET_HEADER_PX,
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
