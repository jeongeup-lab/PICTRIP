import { Text } from "react-native";
import renderer, { act } from "react-test-renderer";
import { useAuthGate } from "@/features/auth/hooks/use-auth-gate";
import { useIsSaved, useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";
import {
  useSaveOptimistic,
  type UseSaveOptimistic,
} from "@/features/saved/hooks/use-save-optimistic";

jest.mock("@/features/auth/hooks/use-auth-gate", () => ({ useAuthGate: jest.fn() }));
jest.mock("@/features/saved/queries", () => ({
  useIsSaved: jest.fn(),
  useSaveMutation: jest.fn(),
  useUnsaveMutation: jest.fn(),
}));

const ID = "123";

function Harness({ onReady }: { onReady: (api: UseSaveOptimistic) => void }) {
  const api = useSaveOptimistic(ID);
  onReady(api);
  return <Text>{String(api.saved)}</Text>;
}

async function mount(): Promise<{ api: () => UseSaveOptimistic }> {
  let last: UseSaveOptimistic;
  await act(async () => {
    renderer.create(<Harness onReady={(a) => (last = a)} />);
  });
  return { api: () => last! };
}

describe("useSaveOptimistic", () => {
  const saveMutateAsync = jest.fn();
  const unsaveMutateAsync = jest.fn();
  const requireAuth = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useAuthGate as jest.Mock).mockReturnValue(requireAuth);
    (useIsSaved as jest.Mock).mockReturnValue(false);
    saveMutateAsync.mockResolvedValue(undefined);
    unsaveMutateAsync.mockResolvedValue(undefined);
    (useSaveMutation as jest.Mock).mockReturnValue({ mutateAsync: saveMutateAsync });
    (useUnsaveMutation as jest.Mock).mockReturnValue({ mutateAsync: unsaveMutateAsync });
  });

  it("returns null without changing state for a guest", async () => {
    requireAuth.mockResolvedValue(false);
    const { api } = await mount();
    let result: boolean | null | undefined;
    await act(async () => {
      result = await api().toggle();
    });
    expect(requireAuth).toHaveBeenCalledWith("save");
    expect(result).toBeNull();
    expect(api().saved).toBe(false);
    expect(saveMutateAsync).not.toHaveBeenCalled();
  });

  it("returns true after save succeeds", async () => {
    requireAuth.mockResolvedValue(true);
    const { api } = await mount();
    let result: boolean | null | undefined;
    await act(async () => {
      result = await api().toggle();
    });
    expect(result).toBe(true);
    expect(api().saved).toBe(true);
    expect(saveMutateAsync).toHaveBeenCalledWith(ID);
  });

  it("rolls back and returns null when save fails", async () => {
    requireAuth.mockResolvedValue(true);
    saveMutateAsync.mockRejectedValue(new Error("save failed"));
    const { api } = await mount();
    let result: boolean | null | undefined;
    await act(async () => {
      result = await api().toggle();
    });
    expect(result).toBeNull();
    expect(api().saved).toBe(false);
  });

  it("returns false after unsave succeeds", async () => {
    requireAuth.mockResolvedValue(true);
    (useIsSaved as jest.Mock).mockReturnValue(true);
    const { api } = await mount();
    let result: boolean | null | undefined;
    await act(async () => {
      result = await api().toggle();
    });
    expect(result).toBe(false);
    expect(api().saved).toBe(false);
    expect(unsaveMutateAsync).toHaveBeenCalledWith(ID);
    expect(saveMutateAsync).not.toHaveBeenCalled();
  });
});
