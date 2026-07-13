import { useEffect, useState } from "react";
import { Image, StyleSheet, View, type LayoutChangeEvent } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";

const CROP = 0.12;
const BACKDROP_BLUR = 26;

interface Size {
  width: number;
  height: number;
}

function fitFrame(img: Size, box: Size) {
  const ratio = img.width / (img.height * (1 - CROP));
  const width = Math.min(box.width, box.height * ratio);
  const height = width / ratio;
  return {
    width,
    height,
    left: (box.width - width) / 2,
    top: (box.height - height) / 2,
  };
}

interface Measure {
  uri: string;
  img: Size | null;
  failed: boolean;
}

export function StoryImage({ uri }: { uri: string | null }) {
  const [measure, setMeasure] = useState<Measure>({ uri: "", img: null, failed: false });
  const [box, setBox] = useState<Size | null>(null);

  useEffect(() => {
    if (!uri) return;
    let alive = true;
    Image.getSize(
      uri,
      (width, height) => {
        if (!alive) return;
        const ok = width > 0 && height > 0;
        setMeasure({ uri, img: ok ? { width, height } : null, failed: !ok });
      },
      () => {
        if (alive) setMeasure({ uri, img: null, failed: true });
      },
    );
    return () => {
      alive = false;
    };
  }, [uri]);

  const measured = measure.uri === uri ? measure : null;
  const img = measured?.img ?? null;
  const sizeFailed = measured?.failed ?? false;

  const onLayout = (e: LayoutChangeEvent) => {
    const { width, height } = e.nativeEvent.layout;
    setBox({ width, height });
  };

  if (sizeFailed) {
    return <RemoteImage uri={uri} style={StyleSheet.absoluteFill} />;
  }

  const frame = img && box ? fitFrame(img, box) : null;

  return (
    <View style={StyleSheet.absoluteFill} onLayout={onLayout}>
      <RemoteImage
        uri={uri}
        style={StyleSheet.absoluteFill}
        cropBanner={false}
        blurRadius={BACKDROP_BLUR}
      />
      <View style={styles.veil} />
      {frame ? (
        <View testID="story-image-frame" style={[styles.frame, frame]}>
          <RemoteImage uri={uri} style={StyleSheet.absoluteFill} />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  veil: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(20,18,22,0.3)",
  },
  frame: { position: "absolute", overflow: "hidden" },
});
