import { useState } from "react";
import {
  Animated,
  Image,
  StyleSheet,
  View,
  type StyleProp,
  type ImageStyle,
  type ViewStyle,
  type ImageResizeMode,
} from "react-native";
import { colors } from "@/constants/theme";

interface RemoteImageProps {
  uri: string | null;
  style?: StyleProp<ImageStyle>;
  radius?: number;
  /**
   * Clip the bottom slice to hide the "한국관광공사" watermark band baked into the
   * bottom of KTO source images. On by default. Set false for full-bleed surfaces
   * that frame the image themselves (spot-detail hero) or letterbox it (PhotoViewer).
   */
  cropBanner?: boolean;
  /**
   * Image `resizeMode`. Only honoured when `cropBanner` is false (the crop path
   * needs its own oversized "cover"). Use "contain" to letterbox (PhotoViewer);
   * defaults to RN's "cover".
   */
  resizeMode?: ImageResizeMode;
  /**
   * Send the Wikimedia hotlink User-Agent with the request. Off by default so
   * every existing KTO caller is untouched. Turn on ONLY for Commons images
   * (upload.wikimedia.org / commons.wikimedia.org) — Android okhttp's default UA
   * is 403-blocked by Wikimedia's robot policy.
   */
  withUA?: boolean;
}

const COMMONS_UA = "PicTrip/1.0 (https://pictrip.org)";

// KTO watermark band is roughly the bottom ~12% of the source frame. The image is
// rendered oversized and top-anchored inside an overflow-clipped box so that slice
// falls below the visible edge. Heuristic — band height varies per image.
const BANNER_FRACTION = 0.12;

const FADE_MS = 220;

export function RemoteImage({
  uri,
  style,
  radius = 0,
  cropBanner = true,
  resizeMode,
  withUA = false,
}: RemoteImageProps) {
  const [failedUri, setFailedUri] = useState<string | null>(null);
  const [opacity] = useState(() => new Animated.Value(0));
  const source =
    uri && withUA ? { uri, headers: { "User-Agent": COMMONS_UA } } : uri ? { uri } : { uri: "" };
  const failed = !!uri && failedUri === uri;
  if (!uri || failed) {
    return (
      <View
        style={[
          { backgroundColor: colors.inset, borderRadius: radius } as ViewStyle,
          style as StyleProp<ViewStyle>,
        ]}
      />
    );
  }
  const resetFade = () => opacity.setValue(0);
  const fadeIn = () =>
    Animated.timing(opacity, { toValue: 1, duration: FADE_MS, useNativeDriver: true }).start();
  const onError = () => setFailedUri(uri);

  if (!cropBanner) {
    const showBackground = resizeMode !== "contain";
    return (
      <View
        style={[
          { borderRadius: radius } as ViewStyle,
          showBackground && ({ backgroundColor: colors.inset } as ViewStyle),
          style as StyleProp<ViewStyle>,
        ]}
      >
        <Animated.View style={[StyleSheet.absoluteFill, { opacity }]}>
          <Image
            source={source}
            onLoadStart={resetFade}
            onLoad={fadeIn}
            onError={onError}
            resizeMode={resizeMode}
            style={[StyleSheet.absoluteFill, { borderRadius: radius }]}
          />
        </Animated.View>
      </View>
    );
  }
  return (
    <View
      style={[
        { borderRadius: radius, overflow: "hidden", backgroundColor: colors.inset } as ViewStyle,
        style as StyleProp<ViewStyle>,
      ]}
    >
      <Animated.View style={[StyleSheet.absoluteFill, { opacity }]}>
        <Image
          source={source}
          onLoadStart={resetFade}
          onLoad={fadeIn}
          onError={onError}
          resizeMode="cover"
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: `${100 / (1 - BANNER_FRACTION)}%`,
          }}
        />
      </Animated.View>
    </View>
  );
}
