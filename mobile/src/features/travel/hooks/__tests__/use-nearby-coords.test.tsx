import { Text } from "react-native";
import renderer, { act } from "react-test-renderer";
import * as location from "@/features/map/usecases/request-location";
import { useNearbyCoords, type UseNearbyCoords } from "@/features/travel/hooks/use-nearby-coords";

jest.mock("@/features/map/usecases/request-location", () => ({
  getPermissionStatus: jest.fn(),
  getCurrentCoords: jest.fn(),
  requestPermission: jest.fn(),
}));

function Harness({ onReady }: { onReady: (value: UseNearbyCoords) => void }) {
  const value = useNearbyCoords();
  onReady(value);
  return <Text>{value.phase}</Text>;
}

async function mount() {
  let current: UseNearbyCoords;
  let tree: renderer.ReactTestRenderer;
  await act(async () => {
    tree = renderer.create(<Harness onReady={(value) => (current = value)} />);
  });
  return { current: () => current!, tree: tree! };
}

function expectState(value: UseNearbyCoords, expected: Omit<UseNearbyCoords, "ask">) {
  expect(value.coords).toEqual(expected.coords);
  expect(value.phase).toBe(expected.phase);
  expect(value.askable).toBe(expected.askable);
}

const coords = { lat: 37.5665, lng: 126.978 };

describe("useNearbyCoords", () => {
  beforeEach(() => jest.clearAllMocks());

  it("becomes ready with a granted permission and location fix", async () => {
    (location.getPermissionStatus as jest.Mock).mockResolvedValue("granted");
    (location.getCurrentCoords as jest.Mock).mockResolvedValue(coords);
    const result = await mount();
    expectState(result.current(), { coords, phase: "ready", askable: false });
  });

  it.each([
    ["denied", false],
    ["undetermined", true],
  ])("becomes unavailable when permission is %s", async (status, askable) => {
    (location.getPermissionStatus as jest.Mock).mockResolvedValue(status);
    const result = await mount();
    expectState(result.current(), { coords: null, phase: "unavailable", askable });
    expect(location.getCurrentCoords).not.toHaveBeenCalled();
  });

  it("becomes unavailable when a granted permission returns no fix", async () => {
    (location.getPermissionStatus as jest.Mock).mockResolvedValue("granted");
    (location.getCurrentCoords as jest.Mock).mockResolvedValue(null);
    const result = await mount();
    expectState(result.current(), { coords: null, phase: "unavailable", askable: false });
  });

  it.each(["permission", "fix"])("becomes unavailable when %s lookup rejects", async (stage) => {
    if (stage === "permission") {
      (location.getPermissionStatus as jest.Mock).mockRejectedValue(new Error("permission"));
    } else {
      (location.getPermissionStatus as jest.Mock).mockResolvedValue("granted");
      (location.getCurrentCoords as jest.Mock).mockRejectedValue(new Error("fix"));
    }
    const result = await mount();
    expectState(result.current(), { coords: null, phase: "unavailable", askable: false });
  });

  it("requests permission and obtains a fix when the user accepts", async () => {
    (location.getPermissionStatus as jest.Mock).mockResolvedValue("undetermined");
    (location.requestPermission as jest.Mock).mockResolvedValue("granted");
    (location.getCurrentCoords as jest.Mock).mockResolvedValue(coords);
    const result = await mount();

    let accepted = false;
    await act(async () => {
      accepted = await result.current().ask();
    });

    expect(accepted).toBe(true);
    expectState(result.current(), { coords, phase: "ready", askable: false });
  });

  it.each(["denied", "error"])(
    "leaves location unavailable when asking ends with %s",
    async (outcome) => {
      (location.getPermissionStatus as jest.Mock).mockResolvedValue("undetermined");
      if (outcome === "denied") {
        (location.requestPermission as jest.Mock).mockResolvedValue("denied");
      } else {
        (location.requestPermission as jest.Mock).mockRejectedValue(new Error("request failed"));
      }
      const result = await mount();

      let accepted = true;
      await act(async () => {
        accepted = await result.current().ask();
      });

      expect(accepted).toBe(false);
      expectState(result.current(), { coords: null, phase: "unavailable", askable: false });
    },
  );

  it("does not update state after unmount", async () => {
    let resolvePermission: (status: string) => void = () => undefined;
    (location.getPermissionStatus as jest.Mock).mockReturnValue(
      new Promise((resolve) => {
        resolvePermission = resolve;
      }),
    );
    const result = await mount();
    expect(result.current().phase).toBe("checking");
    await act(async () => result.tree.unmount());
    await act(async () => resolvePermission("granted"));
    expect(location.getCurrentCoords).not.toHaveBeenCalled();
  });
});
