import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";
import { saveSpot, unsaveSpot } from "@/features/saved/api";

jest.mock("@/features/saved/api", () => ({
  listSaved: jest.fn(),
  saveSpot: jest.fn(),
  unsaveSpot: jest.fn(),
}));

const mockSave = saveSpot as jest.Mock;
const mockUnsave = unsaveSpot as jest.Mock;

function mountMutation(hook: typeof useSaveMutation | typeof useUnsaveMutation) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidated: unknown[][] = [];
  const original = qc.invalidateQueries.bind(qc);
  jest.spyOn(qc, "invalidateQueries").mockImplementation((filters) => {
    invalidated.push((filters?.queryKey ?? []) as unknown[]);
    return original(filters);
  });

  let mutateAsync!: (contentId: string) => Promise<unknown>;
  function Probe() {
    mutateAsync = hook().mutateAsync;
    return <Text>probe</Text>;
  }
  act(() => {
    renderer.create(
      <QueryClientProvider client={qc}>
        <Probe />
      </QueryClientProvider>,
    );
  });
  return { invalidated, run: () => mutateAsync("c1") };
}

beforeEach(() => {
  mockSave.mockResolvedValue(undefined);
  mockUnsave.mockResolvedValue(undefined);
});

afterEach(() => jest.clearAllMocks());

describe("save mutations", () => {
  it("refreshes the AI recommendations after a save, not just the saved list", async () => {
    const { invalidated, run } = mountMutation(useSaveMutation);
    await act(async () => {
      await run();
    });
    expect(invalidated).toContainEqual(["saved"]);
    expect(invalidated).toContainEqual(["home-recommendations"]);
  });

  it("refreshes the AI recommendations after an unsave too", async () => {
    const { invalidated, run } = mountMutation(useUnsaveMutation);
    await act(async () => {
      await run();
    });
    expect(invalidated).toContainEqual(["saved"]);
    expect(invalidated).toContainEqual(["home-recommendations"]);
  });
});
