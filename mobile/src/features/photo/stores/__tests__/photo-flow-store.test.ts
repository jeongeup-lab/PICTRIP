import { usePhotoFlowStore } from "@/features/photo/stores/photo-flow-store";
import { photoSearch } from "@/features/photo/api";
import { getLastKnownCoords } from "@/features/photo/usecases/get-last-known-coords";
import { AppError } from "@/lib/app-error";

jest.mock("@/features/photo/api", () => ({ photoSearch: jest.fn() }));
jest.mock("@/features/photo/usecases/get-last-known-coords", () => ({
  getLastKnownCoords: jest.fn(),
}));

const asset = { uri: "file:///x.jpg", mimeType: "image/jpeg", fileName: "x.jpg" };

describe("photo-flow-store", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    usePhotoFlowStore.getState().reset();
    (getLastKnownCoords as jest.Mock).mockResolvedValue(null);
  });

  it("startSearch transitions loading → success and stores the result", async () => {
    const result = { matches: [], queryHadLocation: false };
    (photoSearch as jest.Mock).mockResolvedValue(result);
    usePhotoFlowStore.getState().setAsset(asset);
    await usePhotoFlowStore.getState().startSearch();
    expect(usePhotoFlowStore.getState().status).toBe("success");
    expect(usePhotoFlowStore.getState().result).toBe(result);
  });

  it("startSearch sets error + errorCode on AppError", async () => {
    (photoSearch as jest.Mock).mockRejectedValue(new AppError("IMAGE_INVALID", "x", 400));
    usePhotoFlowStore.getState().setAsset(asset);
    await usePhotoFlowStore.getState().startSearch();
    expect(usePhotoFlowStore.getState().status).toBe("error");
    expect(usePhotoFlowStore.getState().errorCode).toBe("IMAGE_INVALID");
  });

  it("startSearch is a no-op without an asset", async () => {
    await usePhotoFlowStore.getState().startSearch();
    expect(photoSearch).not.toHaveBeenCalled();
    expect(usePhotoFlowStore.getState().status).toBe("idle");
  });

  it("abort sets status idle and clears the controller", async () => {
    usePhotoFlowStore.getState().setAsset(asset);
    usePhotoFlowStore.getState().abort();
    expect(usePhotoFlowStore.getState().status).toBe("idle");
    expect(usePhotoFlowStore.getState().controller).toBeNull();
  });

  it("reset releases asset and result", async () => {
    usePhotoFlowStore.getState().setAsset(asset);
    usePhotoFlowStore.setState({
      result: { matches: [], queryHadLocation: false },
      status: "success",
    });
    usePhotoFlowStore.getState().reset();
    const s = usePhotoFlowStore.getState();
    expect(s.asset).toBeNull();
    expect(s.result).toBeNull();
    expect(s.status).toBe("idle");
  });
});
