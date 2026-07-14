import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  Image as MeasureImage,
  StyleSheet,
  View,
  type StyleProp,
  type ImageStyle,
  type ViewStyle,
  type ImageResizeMode,
} from "react-native";
import { Image, type ImageContentFit, type ImageLoadEventData } from "expo-image";
import { colors } from "@/constants/theme";

export interface RemoteImageLoad {
  uri: string;
  width: number;
  height: number;
}

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
   * defaults to "cover".
   */
  resizeMode?: ImageResizeMode;
  /**
   * Send the Wikimedia hotlink User-Agent with the request. Off by default so
   * every existing KTO caller is untouched. Turn on ONLY for Commons images
   * (upload.wikimedia.org / commons.wikimedia.org) — Android okhttp's default UA
   * is 403-blocked by Wikimedia's robot policy.
   */
  withUA?: boolean;
  /** Native blur applied to the image (story letterbox backdrop). */
  blurRadius?: number;
  onLoad?: (image: RemoteImageLoad) => void;
}

const COMMONS_UA = "PicTrip/1.0 (https://pictrip.org)";

// KTO watermark band is roughly the bottom ~12% of the source frame. The image is
// rendered oversized and top-anchored inside an overflow-clipped box so that slice
// falls below the visible edge. Heuristic — band height varies per image.
const BANNER_FRACTION = 0.12;

const FADE_MS = 220;

const PREVIEW_BLUR = 6;

// Wikimedia rate-limits bursts (429) while fast-scrolling; a couple of delayed
// remounts recovers those instead of leaving a permanent gray box.
const MAX_RETRIES = 2;
const RETRY_BASE_MS = 900;

// KTO serves the ~1620px original at `_image1_1` and the ~940px mid-size at `_image2_1`;
// backend points large surfaces at the original, which 404s on ~20% of older images. On
// error, degrade to the mid-size once before the generic retry cycle takes over. Scoped to
// the KTO host so a foreign image that merely errors (or happens to carry `_image1_1` in its
// path) keeps its normal same-uri retry instead of being rewritten to a broken URL.
const KTO_HIRES = "_image1_1";
const KTO_MID = "_image2_1";
const KTO_HOST = "tong.visitkorea.or.kr";
const isKtoUrl = (u: string): boolean => {
  const authority = /^https?:\/\/([^/?#]+)/i.exec(u);
  return !!authority && authority[1].toLowerCase() === KTO_HOST;
};
const ktoFallback = (u: string): string | null =>
  isKtoUrl(u) && u.includes(KTO_HIRES) ? u.replace(KTO_HIRES, KTO_MID) : null;

const contentFitFor = (mode?: ImageResizeMode): ImageContentFit => {
  switch (mode) {
    case "contain":
      return "contain";
    case "stretch":
      return "fill";
    case "center":
      return "none";
    default:
      return "cover";
  }
};

export function RemoteImage({
  uri,
  style,
  radius = 0,
  cropBanner = true,
  resizeMode,
  withUA = false,
  blurRadius,
  onLoad,
}: RemoteImageProps) {
  const [failedUri, setFailedUri] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  // The KTO original URI whose _image1_1 has failed and been degraded. Keyed by URI (not a
  // bare boolean) so a stale degrade never bleeds onto a newly-assigned uri in the same render
  // — a fresh uri simply won't match and starts at its own original.
  const [degradedUri, setDegradedUri] = useState<string | null>(null);
  const [prevUri, setPrevUri] = useState(uri);
  const retryRef = useRef<{ uri: string | null; count: number }>({ uri: null, count: 0 });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeUriRef = useRef<string | null>(null);
  const mountedRef = useRef(false);
  // Reset per-uri retry state when the component is reused for a different image
  // (list/story recycling) so a prior image's failure/attempts don't carry over.
  // onError re-keys retryRef by uri; the [uri] effect clears any pending timer.
  if (prevUri !== uri) {
    setPrevUri(uri);
    if (failedUri !== null) setFailedUri(null);
    if (attempt !== 0) setAttempt(0);
  }
  // Effective source: the KTO mid-size only for the exact uri that has been degraded.
  const eff = uri && degradedUri === uri ? (ktoFallback(uri) ?? uri) : uri;
  const lowUri = eff && isKtoUrl(eff) && eff.includes(KTO_HIRES) ? ktoFallback(eff) : null;
  useLayoutEffect(() => {
    activeUriRef.current = eff;
  }, [eff]);
  useLayoutEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  useEffect(() => {
    // Re-key the retry counter to the new uri (incl. A→B→A round-trips, where
    // onError's own uri-mismatch reset never fires) and drop any stale timer.
    retryRef.current = { uri: null, count: 0 };
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [uri]);
  const source = useMemo(
    () =>
      eff && withUA
        ? { uri: eff, headers: { "User-Agent": COMMONS_UA } }
        : eff
          ? { uri: eff }
          : { uri: "" },
    [eff, withUA],
  );
  const handleLoad = useCallback(
    (event: ImageLoadEventData) => {
      if (!eff || activeUriRef.current !== eff) return;
      if (!onLoad) return;
      const loaded = event.source;
      if (loaded?.width && loaded.height) {
        onLoad({ uri: eff, width: loaded.width, height: loaded.height });
        return;
      }
      MeasureImage.getSize(
        eff,
        (width, height) => {
          if (mountedRef.current && activeUriRef.current === eff) {
            onLoad({ uri: eff, width, height });
          }
        },
        () => undefined,
      );
    },
    [eff, onLoad],
  );
  const onError = useCallback(() => {
    // KTO original (_image1_1) missing → degrade to the mid-size once, no backoff.
    if (uri && degradedUri !== uri && ktoFallback(uri)) {
      setDegradedUri(uri);
      setAttempt(0);
      retryRef.current = { uri: null, count: 0 };
      return;
    }
    if (retryRef.current.uri !== eff) retryRef.current = { uri: eff, count: 0 };
    if (retryRef.current.count >= MAX_RETRIES) {
      setFailedUri(eff);
      return;
    }
    retryRef.current.count += 1;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(
      () => setAttempt((a) => a + 1),
      RETRY_BASE_MS * 2 ** (retryRef.current.count - 1),
    );
  }, [degradedUri, eff, uri]);
  const failed = !!eff && failedUri === eff;
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
  const recyclingKey = `${eff}#${attempt}`;

  if (!cropBanner) {
    const contentFit = contentFitFor(resizeMode);
    const showBackground = resizeMode !== "contain";
    return (
      <View
        style={[
          { borderRadius: radius } as ViewStyle,
          showBackground && ({ backgroundColor: colors.inset } as ViewStyle),
          style as StyleProp<ViewStyle>,
        ]}
      >
        {lowUri && (
          <Image
            source={{ uri: lowUri }}
            cachePolicy="memory-disk"
            contentFit={contentFit}
            blurRadius={PREVIEW_BLUR}
            style={[StyleSheet.absoluteFill, { borderRadius: radius }]}
          />
        )}
        <Image
          recyclingKey={recyclingKey}
          source={source}
          cachePolicy="memory-disk"
          transition={FADE_MS}
          onLoad={handleLoad}
          onError={onError}
          contentFit={contentFit}
          blurRadius={blurRadius}
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
      {lowUri && (
        <Image
          source={{ uri: lowUri }}
          cachePolicy="memory-disk"
          contentFit="cover"
          blurRadius={PREVIEW_BLUR}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: `${100 / (1 - BANNER_FRACTION)}%`,
          }}
        />
      )}
      <Image
        recyclingKey={recyclingKey}
        source={source}
        cachePolicy="memory-disk"
        transition={FADE_MS}
        onLoad={handleLoad}
        onError={onError}
        contentFit="cover"
        blurRadius={blurRadius}
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
