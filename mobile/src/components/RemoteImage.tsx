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
  /**
   * Render the KTO ~940px mid-size (`_image2_1`) as the main image instead of the
   * ~1620px original, skipping the blur-up preview. Use on feed surfaces where the
   * mid-size is sharp enough and the original's slower load isn't worth the two-stage
   * fade. No-op for non-KTO uris.
   */
  midSize?: boolean;
  /**
   * Rewrite a Wikimedia Commons thumbnail to this pixel width before loading. Cuts
   * bytes for small grid tiles that would otherwise download the stored 1200px thumb.
   * No-op for non-Commons uris.
   */
  commonsWidth?: number;
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

export const ktoMidSizeUrl = (u: string): string => ktoFallback(u) ?? u;

const COMMONS_HOSTS = new Set(["upload.wikimedia.org", "commons.wikimedia.org"]);
const isCommonsUrl = (u: string): boolean => {
  const authority = /^https?:\/\/([^/?#]+)/i.exec(u);
  return !!authority && COMMONS_HOSTS.has(authority[1].toLowerCase());
};

const IMG_PROXY_ORIGIN = "https://img.pictrip.org";
const PROXY_HOSTS = new Set([...COMMONS_HOSTS, KTO_HOST]);
const proxyUpstream = (u: string): string => {
  const m = /^https?:\/\/([^/?#]+)(.*)$/i.exec(u);
  const host = m?.[1].toLowerCase();
  return m && host && PROXY_HOSTS.has(host) ? `${IMG_PROXY_ORIGIN}/${host}${m[2]}` : u;
};
const unproxyUpstream = (u: string): string | null => {
  if (!u.startsWith(`${IMG_PROXY_ORIGIN}/`)) return null;
  const rest = u.slice(IMG_PROXY_ORIGIN.length + 1);
  const slash = rest.indexOf("/");
  if (slash === -1) return null;
  const host = rest.slice(0, slash);
  return PROXY_HOSTS.has(host) ? `https://${host}${rest.slice(slash)}` : null;
};

export const midSizeSourceUri = (u: string): string => proxyUpstream(ktoMidSizeUrl(u));
const commonsThumb = (u: string, width: number): string => {
  if (u.includes("/thumb/")) return u.replace(/\/(\d+)px-([^/]+)$/, `/${width}px-$2`);
  if (/\/wiki\/Special:FilePath\//i.test(u)) {
    return /[?&]width=\d+/.test(u)
      ? u.replace(/([?&]width=)\d+/, `$1${width}`)
      : `${u}${u.includes("?") ? "&" : "?"}width=${width}`;
  }
  return u;
};

const resolveSource = (
  raw: string | null,
  midSize: boolean,
  commonsWidth: number | undefined,
): string | null => {
  if (!raw) return raw;
  const midResolved = midSize ? ktoMidSizeUrl(raw) : raw;
  const sized =
    commonsWidth && isCommonsUrl(midResolved)
      ? commonsThumb(midResolved, commonsWidth)
      : midResolved;
  return proxyUpstream(sized);
};

const sourceFallback = (u: string): string | null => ktoFallback(u) ?? unproxyUpstream(u);

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
  uri: rawUri,
  style,
  radius = 0,
  cropBanner = true,
  resizeMode,
  withUA = false,
  blurRadius,
  midSize = false,
  commonsWidth,
  onLoad,
}: RemoteImageProps) {
  const uri = resolveSource(rawUri, midSize, commonsWidth);
  const [failedUri, setFailedUri] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  // The URI whose primary source has failed and been degraded to its fallback (KTO _image1_1
  // → _image2_1, proxied Commons → direct Wikimedia). Keyed by URI (not a bare boolean) so a
  // stale degrade never bleeds onto a newly-assigned uri in the same render — a fresh uri
  // simply won't match and starts at its own original.
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
  // Effective source: the fallback only for the exact uri that has been degraded.
  const eff = uri && degradedUri === uri ? (sourceFallback(uri) ?? uri) : uri;
  // Blur-up preview must survive proxying: unwrap a proxied eff to derive the KTO
  // mid-size variant, then re-wrap only if eff itself is proxied (a degraded direct
  // eff means the proxy just failed — keep its preview direct too).
  const effDirect = eff ? (unproxyUpstream(eff) ?? eff) : null;
  const lowDirect =
    effDirect && isKtoUrl(effDirect) && effDirect.includes(KTO_HIRES)
      ? ktoFallback(effDirect)
      : null;
  const lowUri = lowDirect && effDirect !== eff ? proxyUpstream(lowDirect) : lowDirect;
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
    // Primary source failed → degrade to its fallback once, no backoff (KTO original →
    // mid-size, proxied Commons → direct Wikimedia).
    if (uri && degradedUri !== uri && sourceFallback(uri)) {
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
