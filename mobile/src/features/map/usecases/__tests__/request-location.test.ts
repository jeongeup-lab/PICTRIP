import * as Location from "expo-location";
import {
  getPermissionStatus,
  requestPermission,
  getCurrentCoords,
} from "@/features/map/usecases/request-location";

jest.mock("expo-location", () => ({
  getForegroundPermissionsAsync: jest.fn(),
  requestForegroundPermissionsAsync: jest.fn(),
  getCurrentPositionAsync: jest.fn(),
}));

describe("request-location", () => {
  beforeEach(() => jest.clearAllMocks());

  it("getPermissionStatus maps the expo status string", async () => {
    (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
      status: "undetermined",
    });
    expect(await getPermissionStatus()).toBe("undetermined");
  });

  it("requestPermission prompts and maps granted", async () => {
    (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
      status: "granted",
    });
    expect(await requestPermission()).toBe("granted");
    expect(Location.requestForegroundPermissionsAsync).toHaveBeenCalled();
  });

  it("getCurrentCoords returns lat/lng on success", async () => {
    (Location.getCurrentPositionAsync as jest.Mock).mockResolvedValue({
      coords: { latitude: 37.5, longitude: 127.0 },
    });
    expect(await getCurrentCoords()).toEqual({ lat: 37.5, lng: 127.0 });
  });

  it("getCurrentCoords returns null when the fix throws", async () => {
    (Location.getCurrentPositionAsync as jest.Mock).mockRejectedValue(new Error("timeout"));
    expect(await getCurrentCoords()).toBeNull();
  });
});
