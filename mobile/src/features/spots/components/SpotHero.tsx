import type { ReactNode } from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import Svg, { Defs, LinearGradient, Stop, Rect } from "react-native-svg";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon, type IconName } from "@/components/Icon";
import { Gallery } from "@/features/spots/components/Gallery";
import { firstSentence } from "@/features/spots/lib/overview";
import type { SpotDetail } from "@/lib/api-types";
import { colors } from "@/constants/theme";

interface Props {
  data: SpotDetail | undefined;
  /** Controls rendered inside the nav row (glass buttons — see HeroNavButton). */
  nav: ReactNode;
  /** 62 on the full screen (clears the status bar); smaller inside a sheet. */
  navTopPadding: number;
  onViewAll: () => void;
  /** Reports the hero's laid-out height (the detail sheet derives its base snap). */
  onHeroHeight?: (h: number) => void;
}

/** Full-bleed spot hero: KTO image + scrim + glass nav row + title/subline/lead
 * + gallery strip. Shared by the spot-detail screen and the map detail sheet. */
export function SpotHero({ data, nav, navTopPadding, onViewAll, onHeroHeight }: Props) {
  const subline = data
    ? [data.category, [data.regionName, data.sigunguName].filter(Boolean).join(" ")]
        .filter(Boolean)
        .join(" · ")
    : "";
  const lead = firstSentence(data?.overview ?? null);

  return (
    <View
      style={styles.hero}
      onLayout={onHeroHeight ? (e) => onHeroHeight(e.nativeEvent.layout.height) : undefined}
    >
      <RemoteImage uri={data?.firstImageUrl ?? null} style={styles.heroImage} cropBanner={false} />
      <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
        <Defs>
          <LinearGradient id="heroScrim" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#141216" stopOpacity={0.5} />
            <Stop offset="1" stopColor="#141216" stopOpacity={0.62} />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#heroScrim)" />
      </Svg>

      <View style={[styles.nav, { paddingTop: navTopPadding }]}>{nav}</View>

      {data ? (
        <>
          <Text style={styles.title}>{data.title}</Text>
          {subline ? <Text style={styles.subline}>{subline}</Text> : null}
          {lead ? <Text style={styles.desc}>{lead}</Text> : null}
          <Gallery images={data.images} firstImageUrl={data.firstImageUrl} onViewAll={onViewAll} />
        </>
      ) : (
        <View style={styles.heroSkeleton} />
      )}
    </View>
  );
}

export function HeroNavButton({
  icon,
  onPress,
  strokeWidth,
}: {
  icon: IconName;
  onPress: () => void;
  strokeWidth?: number;
}) {
  return (
    <Pressable style={styles.obtn} onPress={onPress} hitSlop={6}>
      <Icon name={icon} size={22} color={colors.onImage} strokeWidth={strokeWidth} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  hero: { backgroundColor: colors.sec, paddingBottom: 22, overflow: "hidden" },
  // Push the KTO image down past the hero's bottom edge so its embedded
  // "한국관광공사" watermark (baked into the bottom-right of the source) is clipped.
  heroImage: { position: "absolute", left: 0, right: 0, top: 0, bottom: -56 },
  nav: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 14,
  },
  obtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.control,
  },
  title: {
    textAlign: "center",
    fontSize: 28,
    fontWeight: "800",
    letterSpacing: -0.6,
    color: colors.onImage,
    marginTop: 26,
    paddingHorizontal: 24,
  },
  subline: {
    textAlign: "center",
    color: colors.onDim,
    fontSize: 16,
    fontWeight: "600",
    marginTop: 12,
  },
  desc: {
    textAlign: "center",
    fontSize: 15,
    lineHeight: 24,
    color: colors.onImage,
    marginTop: 18,
    marginHorizontal: 26,
  },
  heroSkeleton: { height: 300 },
});
