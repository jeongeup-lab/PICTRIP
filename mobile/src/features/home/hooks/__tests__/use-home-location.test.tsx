import { Pressable } from "react-native";
import renderer, { act } from "react-test-renderer";
import { useHomeLocation } from "@/features/home/hooks/use-home-location";
import {
  getCurrentCoords,
  getPermissionStatus,
  requestPermission,
} from "@/features/map/usecases/request-location";

jest.mock("@/features/map/usecases/request-location", () => ({
  getPermissionStatus: jest.fn(),
  getCurrentCoords: jest.fn(),
  requestPermission: jest.fn(),
}));

const mockStatus = getPermissionStatus as jest.Mock;
const mockCoords = getCurrentCoords as jest.Mock;
const mockRequest = requestPermission as jest.Mock;

const FIX = { lat: 37.54, lng: 127.07 };

function Harness() {
  const { coords, status, request } = useHomeLocation();
  return (
    <Pressable
      testID="location"
      accessibilityLabel={status}
      accessibilityHint={coords ? `${coords.lat},${coords.lng}` : "none"}
      onPress={() => void request()}
    />
  );
}

let tree: renderer.ReactTestRenderer | null = null;

async function mount() {
  await act(async () => {
    tree = renderer.create(<Harness />);
  });
  return tree!;
}

const probe = (r: renderer.ReactTestRenderer) => r.root.findByProps({ testID: "location" }).props;

afterEach(() => {
  act(() => tree?.unmount());
  tree = null;
  jest.clearAllMocks();
});

describe("useHomeLocation", () => {
  it("reads a fix straight away when permission is already granted", async () => {
    mockStatus.mockResolvedValue("granted");
    mockCoords.mockResolvedValue(FIX);
    const r = await mount();
    expect(probe(r).accessibilityLabel).toBe("granted");
    expect(probe(r).accessibilityHint).toBe("37.54,127.07");
  });

  it("does not touch the GPS when permission was never asked for", async () => {
    mockStatus.mockResolvedValue("undetermined");
    const r = await mount();
    expect(mockCoords).not.toHaveBeenCalled();
    expect(probe(r).accessibilityLabel).toBe("undetermined");
    expect(probe(r).accessibilityHint).toBe("none");
  });

  it("treats a granted permission with no fix as denied", async () => {
    mockStatus.mockResolvedValue("granted");
    mockCoords.mockResolvedValue(null);
    const r = await mount();
    expect(probe(r).accessibilityLabel).toBe("denied");
    expect(probe(r).accessibilityHint).toBe("none");
  });

  it("picks up coordinates after the user grants permission on request", async () => {
    mockStatus.mockResolvedValue("undetermined");
    mockRequest.mockResolvedValue("granted");
    mockCoords.mockResolvedValue(FIX);
    const r = await mount();
    await act(async () => {
      probe(r).onPress();
    });
    expect(probe(r).accessibilityLabel).toBe("granted");
    expect(probe(r).accessibilityHint).toBe("37.54,127.07");
  });

  it("stays without coordinates when the user refuses the prompt", async () => {
    mockStatus.mockResolvedValue("undetermined");
    mockRequest.mockResolvedValue("denied");
    const r = await mount();
    await act(async () => {
      probe(r).onPress();
    });
    expect(mockCoords).not.toHaveBeenCalled();
    expect(probe(r).accessibilityLabel).toBe("denied");
  });
});
