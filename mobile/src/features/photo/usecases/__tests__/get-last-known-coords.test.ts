jest.mock("expo-location", () => ({
  getForegroundPermissionsAsync: jest.fn(),
  getLastKnownPositionAsync: jest.fn(),
}));

import * as Location from "expo-location";
import { getLastKnownCoords } from "@/features/photo/usecases/get-last-known-coords";

describe("getLastKnownCoords", () => {
  beforeEach(() => jest.clearAllMocks());

  it("returns null and never reads position when permission not granted", async () => {
    (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ granted: false });
    expect(await getLastKnownCoords()).toBeNull();
    expect(Location.getLastKnownPositionAsync).not.toHaveBeenCalled();
  });

  it("returns null when granted but no last-known fix", async () => {
    (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ granted: true });
    (Location.getLastKnownPositionAsync as jest.Mock).mockResolvedValue(null);
    expect(await getLastKnownCoords()).toBeNull();
  });

  it("returns coords when granted and a fix exists", async () => {
    (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ granted: true });
    (Location.getLastKnownPositionAsync as jest.Mock).mockResolvedValue({
      coords: { latitude: 37.5, longitude: 127.0 },
    });
    expect(await getLastKnownCoords()).toEqual({ lat: 37.5, lng: 127.0 });
  });
});
