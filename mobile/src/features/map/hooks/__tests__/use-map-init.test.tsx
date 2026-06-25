import { Text } from "react-native";
import renderer, { act } from "react-test-renderer";
import * as loc from "@/features/map/usecases/request-location";
import { useMapStore } from "@/features/map/stores/map-store";
import { useMapInit, type UseMapInit } from "@/features/map/hooks/use-map-init";
import { SEOUL_CITY_HALL } from "@/constants/map";

jest.mock("@/features/map/usecases/request-location", () => ({
  getPermissionStatus: jest.fn(),
  requestPermission: jest.fn(),
  getCurrentCoords: jest.fn(),
}));

const gps = { lat: 35.1, lng: 129.0 };

/** Renders the hook and exposes its return through a ref-like callback. */
function Harness({ onReady }: { onReady: (api: UseMapInit) => void }) {
  const api = useMapInit();
  onReady(api);
  return <Text>{api.perm}</Text>;
}

async function mount(): Promise<{ api: () => UseMapInit; tree: () => string }> {
  let last: UseMapInit;
  let r: renderer.ReactTestRenderer;
  await act(async () => {
    r = renderer.create(<Harness onReady={(a) => (last = a)} />);
  });
  return { api: () => last!, tree: () => JSON.stringify(r!.toJSON()) };
}

describe("useMapInit", () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    // reset() may re-render a tree still mounted from a prior test; wrap in act.
    await act(async () => {
      useMapStore.getState().reset();
    });
  });

  it("granted entry fetches GPS, anchors it, and goes ready", async () => {
    (loc.getPermissionStatus as jest.Mock).mockResolvedValue("granted");
    (loc.getCurrentCoords as jest.Mock).mockResolvedValue(gps);
    const { api } = await mount();
    expect(loc.getPermissionStatus).toHaveBeenCalledTimes(1);
    expect(api().perm).toBe("ready");
    expect(useMapStore.getState().center).toEqual(gps);
    expect(useMapStore.getState().anchorSource).toBe("gps");
  });

  it("granted entry falls back to Seoul when the fix is null", async () => {
    (loc.getPermissionStatus as jest.Mock).mockResolvedValue("granted");
    (loc.getCurrentCoords as jest.Mock).mockResolvedValue(null);
    await mount();
    expect(useMapStore.getState().center).toEqual(SEOUL_CITY_HALL);
  });

  it("undetermined entry stays on the primer (no prompt, no anchor)", async () => {
    (loc.getPermissionStatus as jest.Mock).mockResolvedValue("undetermined");
    const { api } = await mount();
    expect(api().perm).toBe("undetermined");
    expect(loc.requestPermission).not.toHaveBeenCalled();
    expect(useMapStore.getState().center).toBeNull();
  });

  it("re-entry short-circuits to ready BEFORE calling getPermissionStatus", async () => {
    // Simulate a surviving store from a previous mount.
    await act(async () => {
      useMapStore.getState().setAnchor(gps, "gps", gps);
    });
    const { api } = await mount();
    expect(api().perm).toBe("ready");
    expect(loc.getPermissionStatus).not.toHaveBeenCalled();
    expect(loc.getCurrentCoords).not.toHaveBeenCalled();
  });

  it("allow() prompts and anchors GPS on grant", async () => {
    (loc.getPermissionStatus as jest.Mock).mockResolvedValue("undetermined");
    (loc.requestPermission as jest.Mock).mockResolvedValue("granted");
    (loc.getCurrentCoords as jest.Mock).mockResolvedValue(gps);
    const { api } = await mount();
    await act(async () => {
      await api().allow();
    });
    expect(loc.requestPermission).toHaveBeenCalledTimes(1);
    expect(api().perm).toBe("ready");
    expect(useMapStore.getState().center).toEqual(gps);
  });

  it("allow() marks denied when the prompt is rejected", async () => {
    (loc.getPermissionStatus as jest.Mock).mockResolvedValue("undetermined");
    (loc.requestPermission as jest.Mock).mockResolvedValue("denied");
    const { api } = await mount();
    await act(async () => {
      await api().allow();
    });
    expect(api().perm).toBe("denied");
  });

  it("skipToSeoul() anchors Seoul with source pan and clears gps", async () => {
    (loc.getPermissionStatus as jest.Mock).mockResolvedValue("undetermined");
    const { api } = await mount();
    act(() => api().skipToSeoul());
    expect(api().perm).toBe("ready");
    const st = useMapStore.getState();
    expect(st.center).toEqual(SEOUL_CITY_HALL);
    expect(st.anchorSource).toBe("pan");
    expect(st.gpsCoords).toBeNull();
  });

  it("recenter() reuses an existing GPS fix without re-checking permission", async () => {
    (loc.getPermissionStatus as jest.Mock).mockResolvedValue("granted");
    (loc.getCurrentCoords as jest.Mock).mockResolvedValue(gps);
    const { api } = await mount();
    jest.clearAllMocks();
    await act(async () => {
      await api().recenter();
    });
    expect(loc.getPermissionStatus).not.toHaveBeenCalled();
    expect(useMapStore.getState().center).toEqual(gps);
  });
});
