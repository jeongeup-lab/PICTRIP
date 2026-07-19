import * as ImagePicker from "expo-image-picker";

export interface PickedImage {
  uri: string;
  mimeType: string;
  fileName: string;
}

export type PickResult = PickedImage | "canceled" | "permission-denied";

function toPicked(result: ImagePicker.ImagePickerResult): PickResult {
  if (result.canceled || !result.assets || !result.assets[0]) return "canceled";
  const a = result.assets[0];
  return {
    uri: a.uri,
    mimeType: a.mimeType ?? "image/jpeg",
    fileName: a.fileName ?? "photo.jpg",
  };
}

/** System photo picker — no permission prompt (iOS PHPicker / Android Photo Picker). */
export async function pickFromLibrary(): Promise<PickResult> {
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ["images"],
    allowsMultipleSelection: false,
    quality: 0.8,
  });
  return toPicked(result);
}

/** Camera capture — requests camera permission just-in-time. */
export async function captureFromCamera(): Promise<PickResult> {
  const perm = await ImagePicker.requestCameraPermissionsAsync();
  if (!perm.granted) return "permission-denied";
  const result = await ImagePicker.launchCameraAsync({ quality: 0.8 });
  return toPicked(result);
}
