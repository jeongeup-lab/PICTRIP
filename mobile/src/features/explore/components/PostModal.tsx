import { useState } from "react";
import { Modal, View, Text, Pressable, StyleSheet, useWindowDimensions } from "react-native";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { RemoteImage, fullSizeSourceUri } from "@/components/RemoteImage";
import { Image } from "expo-image";
import { Skeleton } from "@/components/Skeleton";
import { CreditSheet } from "@/features/feed/components/CreditSheet";
import { useMatches } from "@/features/feed/posts-queries";
import type { OverseasPost } from "@/features/feed/posts-api";
import { colors, darkColors } from "@/constants/theme";

const CARD_WIDTH = 335;

export function PostModal({ post, onClose }: { post: OverseasPost; onClose: () => void }) {
  const { width } = useWindowDimensions();
  const cardWidth = Math.min(CARD_WIDTH, width - 40);
  const [creditOpen, setCreditOpen] = useState(false);
  const { data, isLoading } = useMatches(post.id, { enabled: true });
  const matches = data?.matches ?? [];

  const openSpot = (contentId: string) => {
    onClose();
    router.push(`/spots/${contentId}`);
  };

  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.stage}>
        <Pressable
          testID="post-modal-backdrop"
          style={StyleSheet.absoluteFill}
          onPress={onClose}
          accessibilityLabel="닫기"
        />
        <Pressable
          testID="post-modal-close"
          style={styles.close}
          onPress={onClose}
          hitSlop={8}
          accessibilityLabel="닫기"
        >
          <Icon name="close" size={20} color={darkColors.ink} strokeWidth={1.8} />
        </Pressable>

        <View testID="post-modal-card" style={[styles.card, { width: cardWidth }]}>
          <Image
            source={{ uri: fullSizeSourceUri(post.imageUrl) }}
            style={{ width: cardWidth, height: cardWidth }}
            contentFit="cover"
            transition={120}
          />
          <View style={styles.body}>
            <Text style={styles.title} numberOfLines={1}>
              {post.nameKo}, {post.countryNameKo}
            </Text>
            <Text style={styles.desc}>
              {matches.length > 0
                ? `이 분위기와 닮은 국내 여행지 ${matches.length}곳을 찾았어요`
                : isLoading
                  ? "닮은 국내 여행지를 찾고 있어요"
                  : "지금은 닮은 곳을 찾지 못했어요"}
            </Text>
            {isLoading ? (
              <View style={styles.matches}>
                {[0, 1, 2].map((i) => (
                  <View key={i} style={styles.match}>
                    <Skeleton width="100%" height={82} radius={8} />
                  </View>
                ))}
              </View>
            ) : matches.length > 0 ? (
              <View style={styles.matches}>
                {matches.slice(0, 3).map((m) => (
                  <Pressable
                    key={m.contentId}
                    testID={`post-match-${m.contentId}`}
                    style={styles.match}
                    onPress={() => openSpot(m.contentId)}
                  >
                    <RemoteImage uri={m.imageUrl} style={styles.matchImage} radius={8} midSize />
                    <Text style={styles.matchTitle} numberOfLines={1}>
                      {m.title}
                    </Text>
                  </Pressable>
                ))}
              </View>
            ) : null}
            <Pressable
              testID="credit-info"
              onPress={() => setCreditOpen(true)}
              hitSlop={6}
              accessibilityRole="link"
            >
              <Text style={styles.credit} numberOfLines={1}>
                사진 · Wikimedia Commons{post.imageLicense ? ` / ${post.imageLicense}` : ""}
              </Text>
            </Pressable>
          </View>
        </View>

        <CreditSheet visible={creditOpen} post={post} onClose={() => setCreditOpen(false)} />
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  stage: {
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
    backgroundColor: darkColors.glassFill,
    borderWidth: 1,
    borderColor: darkColors.glassBorder,
    zIndex: 2,
  },
  card: {
    borderRadius: 18,
    overflow: "hidden",
    backgroundColor: colors.inset,
    borderWidth: 1,
    borderColor: colors.line,
  },
  body: { paddingTop: 16, paddingHorizontal: 16, paddingBottom: 18 },
  title: { fontSize: 18, fontWeight: "800", letterSpacing: -0.4, color: colors.ink },
  desc: { fontSize: 13, lineHeight: 19, color: colors.sec, marginTop: 6 },
  matches: { flexDirection: "row", gap: 8, marginTop: 14 },
  match: { flex: 1 },
  matchImage: { width: "100%", height: 82 },
  matchTitle: { marginTop: 6, fontSize: 12.5, fontWeight: "700", color: colors.ink },
  credit: { marginTop: 14, fontSize: 11.5, lineHeight: 17, color: colors.ter },
});
