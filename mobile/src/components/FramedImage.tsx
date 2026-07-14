import { useCallback, useState } from "react";
import { StyleSheet, View, type LayoutChangeEvent } from "react-native";
import { RemoteImage, type RemoteImageLoad } from "@/components/RemoteImage";

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
  requestedUri: string;
  image: RemoteImageLoad;
}

export function FramedImage({ uri }: { uri: string | null }) {
  const [measure, setMeasure] = useState<Measure | null>(null);
  const [box, setBox] = useState<Size | null>(null);

  const measured = measure?.requestedUri === uri ? measure.image : null;

  const onLayout = useCallback((e: LayoutChangeEvent) => {
    const { width, height } = e.nativeEvent.layout;
    setBox((current) =>
      current?.width === width && current.height === height ? current : { width, height },
    );
  }, []);

  const onImageLoad = useCallback(
    (image: RemoteImageLoad) => {
      if (image.width <= 0 || image.height <= 0 || !uri) return;
      setMeasure((current) => {
        if (
          current?.requestedUri === uri &&
          current.image.uri === image.uri &&
          current.image.width === image.width &&
          current.image.height === image.height
        ) {
          return current;
        }
        return { requestedUri: uri, image };
      });
    },
    [uri],
  );

  const frame = measured && box ? fitFrame(measured, box) : null;

  return (
    <View style={StyleSheet.absoluteFill} onLayout={onLayout}>
      <RemoteImage
        uri={uri}
        style={StyleSheet.absoluteFill}
        cropBanner={false}
        blurRadius={BACKDROP_BLUR}
        onLoad={onImageLoad}
      />
      <View style={styles.veil} />
      {frame ? (
        <View testID="framed-image-frame" style={[styles.frame, frame]}>
          <RemoteImage uri={measured?.uri ?? null} style={StyleSheet.absoluteFill} />
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
