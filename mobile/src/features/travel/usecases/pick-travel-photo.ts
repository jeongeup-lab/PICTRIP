import * as ImagePicker from "expo-image-picker";
import type { PhotoUpload } from "@/features/travel/api";

const ALLOWED_MIMES = ["image/jpeg", "image/png", "image/webp", "image/heic"];
const FALLBACK_MIME = "image/jpeg";
const FALLBACK_NAME = "travel-photo.jpg";

export function toPhotoUpload(asset: ImagePicker.ImagePickerAsset): PhotoUpload {
  const type =
    asset.mimeType && ALLOWED_MIMES.includes(asset.mimeType) ? asset.mimeType : FALLBACK_MIME;
  return { uri: asset.uri, name: asset.fileName ?? FALLBACK_NAME, type };
}

export async function pickTravelPhoto(): Promise<PhotoUpload | null> {
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ["images"],
    quality: 0.8,
    exif: false,
  });
  const asset = result.canceled ? null : result.assets[0];
  return asset ? toPhotoUpload(asset) : null;
}

export async function shootTravelPhoto(): Promise<PhotoUpload | null> {
  const permission = await ImagePicker.requestCameraPermissionsAsync();
  if (!permission.granted) throw new Error("camera permission denied");
  const result = await ImagePicker.launchCameraAsync({
    mediaTypes: ["images"],
    quality: 0.8,
    exif: false,
  });
  const asset = result.canceled ? null : result.assets[0];
  return asset ? toPhotoUpload(asset) : null;
}
