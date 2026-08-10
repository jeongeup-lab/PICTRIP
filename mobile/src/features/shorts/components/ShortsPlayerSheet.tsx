import { useState } from "react";
import {
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { WebView } from "react-native-webview";
import { Icon } from "@/components/Icon";
import { RemoteImage } from "@/components/RemoteImage";
import { Skeleton } from "@/components/Skeleton";
import type { ShortsCardData, ShortsSpot } from "@/features/shorts/api";
import { colors, radii, spacing } from "@/constants/theme";

interface Props {
  short: ShortsCardData | null;
  onClose: () => void;
}

const PLAYER_BASE_URL = "https://pictrip.org";

function playerHtml(videoId: string): string {
  const params = `autoplay=1&playsinline=1&rel=0&loop=1&playlist=${videoId}`;
  return [
    "<!doctype html><html><head>",
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    "<style>html,body{margin:0;background:#000;height:100%;overflow:hidden}",
    "iframe{width:100%;height:100%;border:0}</style></head><body>",
    `<iframe src="https://www.youtube.com/embed/${videoId}?${params}"`,
    ' allow="autoplay; encrypted-media" allowfullscreen></iframe></body></html>',
  ].join("");
}

export function ShortsPlayerSheet({ short, onClose }: Props) {
  const insets = useSafeAreaInsets();
  const { height: windowHeight } = useWindowDimensions();
  const [playerReady, setPlayerReady] = useState(false);
  const playerHeight = Math.round(windowHeight * 0.54);
  const playerWidth = Math.round((playerHeight * 9) / 16);

  const close = () => {
    setPlayerReady(false);
    onClose();
  };

  const openSpot = (spot: ShortsSpot) => {
    close();
    router.push(`/spots/${spot.contentId}`);
  };

  return (
    <Modal
      visible={short !== null}
      animationType="slide"
      presentationStyle="fullScreen"
      onRequestClose={close}
    >
      <View style={[styles.root, { paddingTop: insets.top }]}>
        <View style={[styles.player, { height: playerHeight }]}>
          {short ? (
            <WebView
              source={{ html: playerHtml(short.videoId), baseUrl: PLAYER_BASE_URL }}
              style={{ width: playerWidth, height: playerHeight, backgroundColor: "#000000" }}
              allowsInlineMediaPlayback
              mediaPlaybackRequiresUserAction={false}
              onShouldStartLoadWithRequest={(request) =>
                !request.isTopFrame ||
                request.url.startsWith(PLAYER_BASE_URL) ||
                request.url.startsWith("about:")
              }
              onLoadEnd={() => setPlayerReady(true)}
              scrollEnabled={false}
            />
          ) : null}
          {!playerReady ? (
            <View style={styles.playerLoading} pointerEvents="none">
              <Skeleton height={playerHeight} radius={0} />
            </View>
          ) : null}
          <Pressable
            testID="shorts-close"
            style={[styles.close, { top: spacing.md }]}
            onPress={close}
            hitSlop={10}
          >
            <Icon name="close" size={18} color={colors.onImage} />
          </Pressable>
        </View>

        <View style={styles.sheet}>
          <View style={styles.sheetHeader}>
            <Text style={styles.sheetTitle}>이 영상 속 장소</Text>
          </View>
          <FlatList
            data={short?.spots ?? []}
            keyExtractor={(spot) => spot.contentId}
            contentContainerStyle={{ paddingBottom: insets.bottom + spacing.lg }}
            renderItem={({ item }) => <SpotRow spot={item} onPress={() => openSpot(item)} />}
            ListEmptyComponent={<Text style={styles.empty}>연결된 장소를 아직 찾지 못했어요</Text>}
          />
        </View>
      </View>
    </Modal>
  );
}

function SpotRow({ spot, onPress }: { spot: ShortsSpot; onPress: () => void }) {
  return (
    <Pressable testID="shorts-spot-row" style={styles.spotRow} onPress={onPress}>
      {spot.imageUrl ? (
        <RemoteImage uri={spot.imageUrl} style={styles.spotImage} radius={radii.lg} />
      ) : (
        <View style={[styles.spotImage, styles.spotImageEmpty]}>
          <Icon name="image" size={18} color={colors.ter} />
        </View>
      )}
      <View style={styles.spotInfo}>
        <Text style={styles.spotTitle} numberOfLines={1}>
          {spot.title}
        </Text>
        <Text style={styles.spotRegion} numberOfLines={1}>
          {spot.regionLabel}
        </Text>
      </View>
      <Icon name="chevron-right" size={16} color={colors.ter} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  player: { backgroundColor: "#000000", alignItems: "center" },
  playerLoading: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0 },
  close: {
    position: "absolute",
    right: spacing.md,
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.control,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  sheet: { flex: 1, borderTopWidth: 1, borderTopColor: colors.line },
  sheetHeader: { paddingHorizontal: spacing.lg, paddingTop: spacing.lg, paddingBottom: spacing.sm },
  sheetTitle: { fontSize: 16, fontWeight: "800", color: colors.ink },
  spotRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  spotImage: { width: 64, height: 64, borderRadius: radii.lg, backgroundColor: colors.inset },
  spotImageEmpty: { alignItems: "center", justifyContent: "center" },
  spotInfo: { flex: 1, gap: 3 },
  spotTitle: { fontSize: 14.5, fontWeight: "700", color: colors.ink },
  spotRegion: { fontSize: 12, color: colors.sec },
  empty: { padding: spacing.xl, textAlign: "center", fontSize: 13, color: colors.ter },
});
