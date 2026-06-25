import { useState } from "react";
import {
  Modal,
  View,
  Text,
  Pressable,
  FlatList,
  useWindowDimensions,
  StyleSheet,
  type NativeSyntheticEvent,
  type NativeScrollEvent,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { colors } from "@/constants/theme";

interface PhotoViewerProps {
  visible: boolean;
  images: string[];
  initialIndex?: number;
  onClose: () => void;
}

/** Full-screen in-app photo gallery: horizontal paging + close + "n / total". */
export function PhotoViewer({ visible, images, initialIndex = 0, onClose }: PhotoViewerProps) {
  const { width, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const [index, setIndex] = useState(initialIndex);

  // Reset paging each time the viewer closes so the next open starts fresh.
  const handleClose = () => {
    setIndex(initialIndex);
    onClose();
  };

  const onMomentumEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const i = width > 0 ? Math.round(e.nativeEvent.contentOffset.x / width) : 0;
    if (i !== index) setIndex(i);
  };

  return (
    <Modal visible={visible} animationType="fade" transparent onRequestClose={handleClose}>
      <View style={styles.root}>
        <FlatList
          // Remount on open so scroll position resets to the initial page.
          key={visible ? "open" : "closed"}
          data={images}
          keyExtractor={(uri, i) => `${uri}-${i}`}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          initialScrollIndex={images.length > 0 ? initialIndex : undefined}
          getItemLayout={(_, i) => ({ length: width, offset: width * i, index: i })}
          onMomentumScrollEnd={onMomentumEnd}
          renderItem={({ item }) => (
            <View style={[styles.page, { width, height }]}>
              <RemoteImage
                uri={item}
                style={{ width, height: height * 0.8, resizeMode: "contain" }}
              />
            </View>
          )}
        />

        <Pressable
          style={[styles.close, { top: insets.top + 8 }]}
          onPress={handleClose}
          hitSlop={10}
          accessibilityLabel="닫기"
        >
          <Icon name="close" size={24} color={colors.onImage} />
        </Pressable>

        {images.length > 1 ? (
          <View style={[styles.counter, { bottom: insets.bottom + 24 }]} pointerEvents="none">
            <Text style={styles.counterText}>
              {Math.min(index, images.length - 1) + 1} / {images.length}
            </Text>
          </View>
        ) : null}
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "rgba(0,0,0,0.96)" },
  page: { alignItems: "center", justifyContent: "center" },
  close: {
    position: "absolute",
    right: 16,
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.control,
  },
  counter: { position: "absolute", left: 0, right: 0, alignItems: "center" },
  counterText: {
    color: colors.onImage,
    fontSize: 14,
    fontWeight: "700",
    backgroundColor: colors.control,
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 999,
    overflow: "hidden",
  },
});
