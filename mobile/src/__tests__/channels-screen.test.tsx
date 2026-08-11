import renderer, { act } from "react-test-renderer";
import ChannelsScreen from "@/app/channels";
import { useLocalSearchParams } from "expo-router";

jest.mock("expo-router", () => ({ useLocalSearchParams: jest.fn() }));
jest.mock("@/features/channels/components/StoryViewer", () => ({
  StoryViewer: jest.fn(() => null),
}));

const useLocalSearchParamsMock = useLocalSearchParams as jest.Mock;
const { StoryViewer } = jest.requireMock("@/features/channels/components/StoryViewer") as {
  StoryViewer: jest.Mock;
};

afterEach(() => jest.clearAllMocks());

const startProp = () => StoryViewer.mock.calls[0][0].start as string;

async function mount() {
  let tree: renderer.ReactTestRenderer;
  await act(async () => {
    tree = renderer.create(<ChannelsScreen />);
  });
  return tree!;
}

describe("ChannelsScreen", () => {
  it("passes a valid start channel through unchanged", async () => {
    useLocalSearchParamsMock.mockReturnValue({ start: "hidden" });
    await mount();
    expect(startProp()).toBe("hidden");
  });

  it("falls back to hidden for an invalid start deeplink", async () => {
    useLocalSearchParamsMock.mockReturnValue({ start: "evil" });
    await mount();
    expect(startProp()).toBe("hidden");
  });

  it("falls back to hidden when no start is provided", async () => {
    useLocalSearchParamsMock.mockReturnValue({});
    await mount();
    expect(startProp()).toBe("hidden");
  });
});
