import * as ImagePicker from "expo-image-picker";

import { pickFromLibrary, captureFromCamera } from "@/features/photo/usecases/pick-image";

jest.mock("expo-image-picker", () => ({
  launchImageLibraryAsync: jest.fn(),
  launchCameraAsync: jest.fn(),
  requestCameraPermissionsAsync: jest.fn(),
}));

const asset = { uri: "file:///a.jpg", mimeType: "image/png", fileName: "a.png" };

describe("pick-image", () => {
  beforeEach(() => jest.clearAllMocks());

  it("library pick maps the first asset and never requests camera permission", async () => {
    (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValue({
      canceled: false,
      assets: [asset],
    });
    expect(await pickFromLibrary()).toEqual({
      uri: "file:///a.jpg",
      mimeType: "image/png",
      fileName: "a.png",
    });
    expect(ImagePicker.requestCameraPermissionsAsync).not.toHaveBeenCalled();
  });

  it("library cancel returns 'canceled'", async () => {
    (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValue({
      canceled: true,
      assets: null,
    });
    expect(await pickFromLibrary()).toBe("canceled");
  });

  it("camera requests permission and returns 'permission-denied' when refused", async () => {
    (ImagePicker.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({ granted: false });
    expect(await captureFromCamera()).toBe("permission-denied");
    expect(ImagePicker.launchCameraAsync).not.toHaveBeenCalled();
  });

  it("camera captures when granted", async () => {
    (ImagePicker.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({ granted: true });
    (ImagePicker.launchCameraAsync as jest.Mock).mockResolvedValue({
      canceled: false,
      assets: [asset],
    });
    expect(await captureFromCamera()).toEqual({
      uri: "file:///a.jpg",
      mimeType: "image/png",
      fileName: "a.png",
    });
  });

  it("falls back to defaults when asset omits mime/name", async () => {
    (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValue({
      canceled: false,
      assets: [{ uri: "file:///b" }],
    });
    expect(await pickFromLibrary()).toEqual({
      uri: "file:///b",
      mimeType: "image/jpeg",
      fileName: "photo.jpg",
    });
  });
});
