import { Rail } from "@/components/Rail";
import { RemoteImage } from "@/components/RemoteImage";
import type { SpotImage } from "@/lib/api-types";
import { radii } from "@/constants/theme";

export function Gallery({ images }: { images: SpotImage[] }) {
  if (images.length === 0) return null;
  return (
    <Rail gap={10}>
      {images.map((img, i) => (
        <RemoteImage
          key={`${img.originImageUrl}-${i}`}
          uri={img.smallImageUrl ?? img.originImageUrl}
          radius={radii.md}
          style={{ width: i === 0 ? 240 : 140, height: 160 }}
        />
      ))}
    </Rail>
  );
}
