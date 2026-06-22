import { api } from "@/lib/api-client";
import type { Coords } from "@/features/photo/usecases/get-last-known-coords";
import type { PickedImage } from "@/features/photo/usecases/pick-image";
import type { PhotoSearchResult } from "@/lib/api-types";

/** POST the photo as multipart/form-data. api-client already unwraps JSend, so
 * the result is returned as-is (no re-unwrap). The image bytes are uploaded
 * once and never persisted (KTO). RN sets the multipart boundary itself. */
export async function photoSearch(
  asset: PickedImage,
  coords: Coords | null,
  signal?: AbortSignal,
): Promise<PhotoSearchResult> {
  const form = new FormData();
  const filePart = { uri: asset.uri, name: asset.fileName, type: asset.mimeType };
  form.append("image", filePart as unknown as Blob);
  return (await api.post("/taste/photo-search", form, {
    params: coords ? { lat: coords.lat, lng: coords.lng } : undefined,
    headers: { "Content-Type": "multipart/form-data" },
    signal,
  })) as unknown as PhotoSearchResult;
}
