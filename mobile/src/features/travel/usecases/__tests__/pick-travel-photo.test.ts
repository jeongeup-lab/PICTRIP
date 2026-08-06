import * as ImagePicker from "expo-image-picker";
import {
  pickTravelPhoto,
  shootTravelPhoto,
  toPhotoUpload,
} from "@/features/travel/usecases/pick-travel-photo";

jest.mock("expo-image-picker", () => ({
  launchImageLibraryAsync: jest.fn(),
  requestCameraPermissionsAsync: jest.fn(),
  launchCameraAsync: jest.fn(),
}));

const launch = ImagePicker.launchImageLibraryAsync as jest.Mock;
const requestCamera = ImagePicker.requestCameraPermissionsAsync as jest.Mock;
const launchCamera = ImagePicker.launchCameraAsync as jest.Mock;

describe("pickTravelPhoto", () => {
  beforeEach(() => jest.clearAllMocks());

  it("returns null when selection is canceled", async () => {
    launch.mockResolvedValue({ canceled: true, assets: null });
    await expect(pickTravelPhoto()).resolves.toBeNull();
  });

  it.each(["image/jpeg", "image/png", "image/webp", "image/heic"])(
    "keeps the supported MIME %s",
    (mimeType) => {
      expect(toPhotoUpload({ uri: "file:///photo", fileName: "photo", mimeType } as never)).toEqual(
        { uri: "file:///photo", name: "photo", type: mimeType },
      );
    },
  );

  it("uses fallback name and MIME when metadata is missing", () => {
    expect(
      toPhotoUpload({ uri: "file:///photo", fileName: null, mimeType: null } as never),
    ).toEqual({ uri: "file:///photo", name: "travel-photo.jpg", type: "image/jpeg" });
  });

  it("throws when the picker reports an unsupported MIME", () => {
    expect(() =>
      toPhotoUpload({
        uri: "file:///photo",
        fileName: "photo.gif",
        mimeType: "image/gif",
      } as never),
    ).toThrow("Unsupported image MIME type: image/gif");
  });

  it("propagates picker rejection", async () => {
    const error = new Error("picker failed");
    launch.mockRejectedValue(error);
    await expect(pickTravelPhoto()).rejects.toBe(error);
  });

  it("rejects shooting when camera permission is denied", async () => {
    requestCamera.mockResolvedValue({ granted: false });

    await expect(shootTravelPhoto()).rejects.toThrow("camera permission denied");
    expect(launchCamera).not.toHaveBeenCalled();
  });

  it("returns null when camera capture is canceled", async () => {
    requestCamera.mockResolvedValue({ granted: true });
    launchCamera.mockResolvedValue({ canceled: true, assets: null });

    await expect(shootTravelPhoto()).resolves.toBeNull();
  });

  it("converts a captured camera asset", async () => {
    requestCamera.mockResolvedValue({ granted: true });
    launchCamera.mockResolvedValue({
      canceled: false,
      assets: [{ uri: "file:///shot.jpg", fileName: "shot.jpg", mimeType: "image/jpeg" }],
    });

    await expect(shootTravelPhoto()).resolves.toEqual({
      uri: "file:///shot.jpg",
      name: "shot.jpg",
      type: "image/jpeg",
    });
  });
});
