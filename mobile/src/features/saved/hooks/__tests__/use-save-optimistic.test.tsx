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
  const saveMutate = jest.fn();
  const unsaveMutate = jest.fn();
  const requireAuth = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useAuthGate as jest.Mock).mockReturnValue(requireAuth);
    (useIsSaved as jest.Mock).mockReturnValue(false);
    (useSaveMutation as jest.Mock).mockReturnValue({ mutate: saveMutate });
    (useUnsaveMutation as jest.Mock).mockReturnValue({ mutate: unsaveMutate });
  });

  it("auth-gates BEFORE optimistic flip — no phantom heart for guests", async () => {
    requireAuth.mockResolvedValue(false);
    const { api } = await mount();
    await act(async () => {
      await api().toggle();
    });
    expect(requireAuth).toHaveBeenCalledWith("save");
    expect(api().saved).toBe(false); // never flipped
    expect(saveMutate).not.toHaveBeenCalled();
  });

  it("flips optimistically and fires save when authed", async () => {
    requireAuth.mockResolvedValue(true);
    const { api } = await mount();
    await act(async () => {
      await api().toggle();
    });
    expect(api().saved).toBe(true);
    expect(saveMutate).toHaveBeenCalledWith(
      ID,
      expect.objectContaining({ onError: expect.any(Function) }),
    );
  });

  it("rolls back the optimistic flip when the mutation errors", async () => {
    requireAuth.mockResolvedValue(true);
    const { api } = await mount();
    await act(async () => {
      await api().toggle();
    });
    expect(api().saved).toBe(true);
    // invoke the onError rollback passed to the mutation
    const opts = saveMutate.mock.calls[0][1];
    act(() => opts.onError());
    expect(api().saved).toBe(false);
  });

  it("uses unsave when already saved", async () => {
    requireAuth.mockResolvedValue(true);
    (useIsSaved as jest.Mock).mockReturnValue(true);
    const { api } = await mount();
    await act(async () => {
      await api().toggle();
    });
    expect(api().saved).toBe(false);
    expect(unsaveMutate).toHaveBeenCalledWith(ID, expect.any(Object));
    expect(saveMutate).not.toHaveBeenCalled();
  });
});
