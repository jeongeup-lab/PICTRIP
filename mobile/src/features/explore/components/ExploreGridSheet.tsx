import { useMemo, useState } from "react";
import {
  FlatList,
  Pressable,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import Svg, { Defs, LinearGradient, Rect, Stop } from "react-native-svg";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Icon } from "@/components/Icon";
import { RemoteImage } from "@/components/RemoteImage";
import { toGridBlocks, type GridBlock } from "@/features/explore/lib/grid-blocks";
import {
  continentsPresent,
  filterByContinent,
  type Continent,
} from "@/features/explore/lib/continents";
import type { OverseasPost } from "@/features/explore/api";
import { commonsWidthFor } from "@/lib/commons-width";
import { colors, spacing } from "@/constants/theme";

export const SHEET_TITLE = "탐색";
export const ALL_LABEL = "전체";
export const EMPTY_TEXT = "이 지역의 사진이 아직 없어요.";

const GAP = 2;

interface Props {
  posts: OverseasPost[];
  onPick: (index: number) => void;
  onClose: () => void;
  onEndReached: () => void;
}

export function ExploreGridSheet({ posts, onPick, onClose, onEndReached }: Props) {
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const [continent, setContinent] = useState<Continent | null>(null);

  const available = useMemo(() => continentsPresent(posts), [posts]);
  const shown = useMemo(() => filterByContinent(posts, continent), [posts, continent]);
  const indexOf = useMemo(() => {
    const table = new Map<number, number>();
    posts.forEach((post, at) => table.set(post.id, at));
    return table;
  }, [posts]);

  const { blocks, leftover } = useMemo(() => toGridBlocks(shown), [shown]);

  const unit = (width - GAP * 2) / 3;
  const bigSize = unit * 2 + GAP;

  const tile = (post: OverseasPost, size: number) => (
    <Pressable
      key={post.id}
      testID="explore-grid-tile"
      accessibilityRole="button"
      accessibilityLabel={`${post.countryNameKo} ${post.nameKo}`}
      style={{ width: size, height: size }}
      onPress={() => onPick(indexOf.get(post.id) ?? 0)}
    >
      <RemoteImage
        uri={post.imageUrl}
        withUA
        cropBanner={false}
        commonsWidth={commonsWidthFor(size)}
        style={{ width: size, height: size }}
      />
      <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
        <Defs>
          <LinearGradient id="gridTileScrim" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0.56" stopColor="#0A0C10" stopOpacity={0} />
            <Stop offset="1" stopColor="#0A0C10" stopOpacity={0.64} />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#gridTileScrim)" />
      </Svg>
      <Text style={styles.label} numberOfLines={1}>
        {post.countryNameKo} · {post.nameKo}
      </Text>
    </Pressable>
  );

  const renderBlock = ({ item }: { item: GridBlock }) => {
    if (item.type === "row3") {
      return <View style={styles.row}>{item.items.map((post) => tile(post, unit))}</View>;
    }
    return (
      <View style={styles.row}>
        {tile(item.big, bigSize)}
        <View style={styles.sideCol}>{item.side.map((post) => tile(post, unit))}</View>
      </View>
    );
  };

  return (
    <View testID="explore-grid-sheet" style={styles.root}>
      <StatusBar barStyle="dark-content" />

      <View style={[styles.head, { paddingTop: insets.top + 10 }]}>
        <Text style={styles.title}>{SHEET_TITLE}</Text>
        <Pressable
          testID="explore-grid-close"
          accessibilityRole="button"
          accessibilityLabel="격자 닫기"
          hitSlop={8}
          onPress={onClose}
        >
          <Icon name="close" size={20} color={colors.ink} strokeWidth={2} />
        </Pressable>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chips}
        style={styles.chipTrack}
      >
        <Chip label={ALL_LABEL} on={continent === null} onPress={() => setContinent(null)} />
        {available.map((name) => (
          <Chip
            key={name}
            label={name}
            on={continent === name}
            onPress={() => setContinent(name)}
          />
        ))}
      </ScrollView>

      {shown.length === 0 ? (
        <Text style={styles.empty}>{EMPTY_TEXT}</Text>
      ) : (
        <FlatList
          data={blocks}
          keyExtractor={(block) =>
            block.type === "big" ? `big-${block.big.id}` : `row3-${block.items[0].id}`
          }
          renderItem={renderBlock}
          showsVerticalScrollIndicator={false}
          onEndReached={onEndReached}
          onEndReachedThreshold={0.6}
          ListFooterComponent={
            leftover.length > 0 ? (
              <View style={styles.row}>{leftover.map((post) => tile(post, unit))}</View>
            ) : null
          }
        />
      )}
    </View>
  );
}

function Chip({ label, on, onPress }: { label: string; on: boolean; onPress: () => void }) {
  return (
    <Pressable
      testID={`explore-continent-${label}`}
      accessibilityRole="button"
      accessibilityState={{ selected: on }}
      style={({ pressed }) => [styles.chip, on && styles.chipOn, pressed && styles.pressed]}
      onPress={onPress}
    >
      <Text style={[styles.chipText, on && styles.chipTextOn]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0, backgroundColor: colors.bg },
  head: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  title: { fontSize: 22, fontWeight: "800", letterSpacing: -0.7, color: colors.ink },
  chipTrack: { flexGrow: 0 },
  chips: { gap: 8, paddingHorizontal: spacing.lg, paddingBottom: spacing.md },
  chip: {
    height: 34,
    paddingHorizontal: 14,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: "center",
    justifyContent: "center",
  },
  chipOn: { backgroundColor: colors.ink, borderColor: colors.ink },
  chipText: { fontSize: 13, fontWeight: "700", letterSpacing: -0.2, color: colors.sec },
  chipTextOn: { color: colors.bg },
  row: { flexDirection: "row", gap: GAP, marginBottom: GAP },
  sideCol: { gap: GAP, justifyContent: "space-between" },
  label: {
    position: "absolute",
    left: 6,
    right: 6,
    bottom: 5,
    fontSize: 9.5,
    fontWeight: "700",
    letterSpacing: -0.1,
    color: colors.onImage,
    textShadowColor: "rgba(0,0,0,0.6)",
    textShadowRadius: 4,
  },
  empty: { paddingHorizontal: spacing.lg, paddingTop: spacing.xl, fontSize: 14, color: colors.sec },
  pressed: { opacity: 0.7 },
});
