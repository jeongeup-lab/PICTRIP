import { useEffect, useRef, useState } from "react";
import { StyleSheet, View, type StyleProp, type ImageStyle, type ViewStyle } from "react-native";
import { Image, type ImageContentFit } from "expo-image";
import { colors } from "@/constants/theme";

type LegacyResizeMode = "cover" | "contain" | "stretch" | "center";

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
   * Legacy RN `resizeMode`, mapped to expo-image `contentFit`. Only honoured when
   * `cropBanner` is false (the crop path needs its own oversized "cover"). Use
   * "contain" to letterbox (PhotoViewer); defaults to "cover".
   */
  resizeMode?: LegacyResizeMode;
  /**
   * Send the Wikimedia hotlink User-Agent with the request. Off by default so
   * every existing KTO caller is untouched. Turn on ONLY for Commons images
   * (upload.wikimedia.org / commons.wikimedia.org) — Android okhttp's default UA
   * is 403-blocked by Wikimedia's robot policy.
   */
  withUA?: boolean;
  /** Native blur applied to the image (story letterbox backdrop). */
  blurRadius?: number;
}

const COMMONS_UA = "PicTrip/1.0 (https://pictrip.org)";

// KTO watermark band is roughly the bottom ~12% of the source frame. The image is
// rendered oversized and top-anchored inside an overflow-clipped box so that slice
// falls below the visible edge. Heuristic — band height varies per image.
const BANNER_FRACTION = 0.12;

const FADE_MS = 220;

// Wikimedia rate-limits bursts (429) while fast-scrolling; a couple of delayed
// remounts recovers those instead of leaving a permanent gray box.
const MAX_RETRIES = 2;
const RETRY_BASE_MS = 900;

function contentFitFor(resizeMode: LegacyResizeMode | undefined): ImageContentFit {
  return resizeMode === "contain" ? "contain" : "cover";
}

export function RemoteImage({
  uri,
  style,
  radius = 0,
  cropBanner = true,
  resizeMode,
  withUA = false,
  blurRadius,
}: RemoteImageProps) {
  const [failedUri, setFailedUri] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [prevUri, setPrevUri] = useState(uri);
  const retryRef = useRef<{ uri: string | null; count: number }>({ uri: null, count: 0 });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Reset per-uri retry state when the component is reused for a different image
  // (list/story recycling) so a prior image's failure/attempts don't carry over.
  // onError re-keys retryRef by uri; the [uri] effect clears any pending timer.
  if (prevUri !== uri) {
    setPrevUri(uri);
    if (failedUri !== null) setFailedUri(null);
    if (attempt !== 0) setAttempt(0);
  }
  useEffect(() => {
    // Re-key the retry counter to the new uri (incl. A→B→A round-trips, where
    // onError's own uri-mismatch reset never fires) and drop any stale timer.
    retryRef.current = { uri: null, count: 0 };
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [uri]);

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

  const source = withUA ? { uri, headers: { "User-Agent": COMMONS_UA } } : { uri };
  const onError = () => {
    if (retryRef.current.uri !== uri) retryRef.current = { uri, count: 0 };
    if (retryRef.current.count >= MAX_RETRIES) {
      setFailedUri(uri);
      return;
    }
    retryRef.current.count += 1;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(
      () => setAttempt((a) => a + 1),
      RETRY_BASE_MS * 2 ** (retryRef.current.count - 1),
    );
  };
  const attemptKey = `${uri}#${attempt}`;

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
        <Image
          key={attemptKey}
          source={source}
          onError={onError}
          contentFit={contentFitFor(resizeMode)}
          blurRadius={blurRadius}
          transition={FADE_MS}
          cachePolicy="memory-disk"
          recyclingKey={uri}
          style={[StyleSheet.absoluteFill, { borderRadius: radius }]}
        />
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
      <Image
        key={attemptKey}
        source={source}
        onError={onError}
        contentFit="cover"
        contentPosition="top"
        blurRadius={blurRadius}
        transition={FADE_MS}
        cachePolicy="memory-disk"
        recyclingKey={uri}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: `${100 / (1 - BANNER_FRACTION)}%`,
        }}
      />
    </View>
  );
}
