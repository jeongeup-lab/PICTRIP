import { useCallback, useMemo, useState } from "react";
import {
  View,
  FlatList,
  Pressable,
  RefreshControl,
  StatusBar,
  useWindowDimensions,
  StyleSheet,
} from "react-native";
import Svg, { Defs, LinearGradient, Stop, Rect } from "react-native-svg";
import { RemoteImage } from "@/components/RemoteImage";
import { useExploreFeed } from "@/features/explore/queries";
import { toGridBlocks, type GridBlock } from "@/features/explore/lib/grid-blocks";
import { PostModal } from "@/features/explore/components/PostModal";
import type { OverseasPost } from "@/features/feed/posts-api";
import { makeSeed } from "@/lib/seed";
import { colors } from "@/constants/theme";

const GAP = 2;
const SCRIM_HEIGHT = 92;

export function ExploreGrid() {
  const { width } = useWindowDimensions();
  const [seed, setSeed] = useState(() => makeSeed());
  const [selected, setSelected] = useState<OverseasPost | null>(null);

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isRefetching } =
    useExploreFeed(seed);

  const { blocks, leftover } = useMemo(() => {
    const items = data?.pages.flatMap((p) => p.items) ?? [];
    return toGridBlocks(items);
  }, [data]);

  const tailItems = hasNextPage ? [] : leftover;

  const unit = (width - GAP * 2) / 3;
  const bigSize = unit * 2 + GAP;

  const onRefresh = useCallback(() => setSeed(makeSeed()), []);

  const onEndReached = () => {
    if (hasNextPage && !isFetchingNextPage) void fetchNextPage();
  };

  const tile = (post: OverseasPost, size: number) => (
    <Pressable
      key={post.id}
      testID="explore-tile"
      onPress={() => setSelected(post)}
      style={{ width: size, height: size }}
    >
      <RemoteImage
        uri={post.imageUrl}
        withUA
        cropBanner={false}
        style={{ width: size, height: size }}
      />
    </Pressable>
  );

  const renderBlock = ({ item }: { item: GridBlock }) => {
    if (item.type === "row3") {
      return <View style={styles.row}>{item.items.map((p) => tile(p, unit))}</View>;
    }
    return (
      <View style={styles.row}>
        {tile(item.big, bigSize)}
        <View style={styles.sideCol}>{item.side.map((p) => tile(p, unit))}</View>
      </View>
    );
  };

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <FlatList
        data={blocks}
        keyExtractor={(b) => (b.type === "big" ? `big-${b.big.id}` : `row3-${b.items[0].id}`)}
        renderItem={renderBlock}
        showsVerticalScrollIndicator={false}
        onEndReached={onEndReached}
        onEndReachedThreshold={0.6}
        ListFooterComponent={
          tailItems.length > 0 ? (
            <View style={styles.row}>{tailItems.map((p) => tile(p, unit))}</View>
          ) : null
        }
        refreshControl={
          <RefreshControl
            refreshing={isRefetching}
            onRefresh={onRefresh}
            tintColor={colors.onImage}
          />
        }
      />

      <View style={styles.scrim} pointerEvents="none">
        <Svg width="100%" height="100%">
          <Defs>
            <LinearGradient id="exploreScrim" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor="#141216" stopOpacity={0.55} />
              <Stop offset="1" stopColor="#141216" stopOpacity={0} />
            </LinearGradient>
          </Defs>
          <Rect x="0" y="0" width="100%" height="100%" fill="url(#exploreScrim)" />
        </Svg>
      </View>

      {selected ? <PostModal post={selected} onClose={() => setSelected(null)} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.ink },
  row: { flexDirection: "row", gap: GAP, marginBottom: GAP },
  sideCol: { gap: GAP, justifyContent: "space-between" },
  scrim: { position: "absolute", top: 0, left: 0, right: 0, height: SCRIM_HEIGHT },
});
