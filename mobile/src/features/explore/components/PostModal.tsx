import { Modal, View, Pressable, StyleSheet } from "react-native";
import { PostCarousel } from "@/features/feed/components/PostCarousel";
import { Icon } from "@/components/Icon";
import type { OverseasPost } from "@/features/feed/posts-api";
import { colors } from "@/constants/theme";

export function PostModal({ post, onClose }: { post: OverseasPost; onClose: () => void }) {
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <Pressable
        testID="post-modal-backdrop"
        style={styles.backdrop}
        onPress={onClose}
        accessibilityLabel="닫기"
      >
        <Pressable
          testID="post-modal-close"
          style={styles.close}
          onPress={onClose}
          hitSlop={8}
          accessibilityLabel="닫기"
        >
          <Icon name="close" size={20} color={colors.onImage} strokeWidth={1.8} />
        </Pressable>
        <View testID="post-modal-sheet" onStartShouldSetResponder={() => true}>
          <PostCarousel post={post} onNavigate={onClose} />
        </View>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(16,14,18,0.92)",
    alignItems: "center",
    justifyContent: "center",
  },
  close: {
    position: "absolute",
    top: 56,
    right: 20,
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.glassFill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    zIndex: 2,
  },
});
