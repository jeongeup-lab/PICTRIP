import renderer, { act } from "react-test-renderer";
import PlacesScreen from "@/app/plan/places";
import type { ImportResult, PlaceType, ResolvedPlace, ResolveStatus } from "@/features/plan/api";
import { useAssembleMutation } from "@/features/plan/queries";
import { usePlanDraft } from "@/features/plan/stores/plan-draft-store";

jest.mock("expo-router", () => ({
  router: { back: jest.fn(), push: jest.fn(), replace: jest.fn() },
}));
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: (props: { children?: unknown }) => props.children,
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/features/plan/queries", () => ({ useAssembleMutation: jest.fn() }));

const useAssembleMock = useAssembleMutation as jest.Mock;

const place = (
  name: string,
  status: ResolveStatus = "matched",
  placeType: PlaceType = "attraction",
): ResolvedPlace => ({
  extracted: { name, nameKo: null, placeType, regionHint: null, tip: null, orderHint: null },
  spot:
    status === "unmatched"
      ? null
      : {
          source: "kto",
          contentId: name,
          title: name,
          category: null,
          address: null,
          lat: null,
          lng: null,
          imageUrl: null,
        },
  confidence: 1,
  status,
});

const imported: ImportResult = {
  sourceKind: "youtube",
  sourceTitle: "통영 브이로그",
  tripDays: 2,
  places: [
    place("동피랑"),
    place("경상남도", "matched", "region"),
    place("케이블카"),
    place("어딘가", "unmatched"),
  ],
};

let mutate: jest.Mock;
let tree: renderer.ReactTestRenderer | null = null;

const render = () => {
  act(() => {
    tree = renderer.create(<PlacesScreen />);
  });
  return tree!;
};

const text = (r: renderer.ReactTestRenderer) => JSON.stringify(r.toJSON());

beforeEach(() => {
  jest.clearAllMocks();
  mutate = jest.fn();
  useAssembleMock.mockReturnValue({ mutate, isPending: false });
  act(() => usePlanDraft.getState().startImportFlow(imported, "https://youtu.be/x"));
});

afterEach(() => {
  act(() => tree?.unmount());
  tree = null;
});

describe("plan places screen", () => {
  it("counts only visitable places — regions and unmatched rows are excluded", () => {
    const body = text(render());
    expect(body).toContain("영상에서 ");
    expect(body).toContain("정보를 못 찾은 ");
    expect(body).not.toContain("경상남도");
  });

  it("announces the day count the video implied", () => {
    expect(text(render())).toContain("1박 2일");
  });

  it("keeps the missing places collapsed until asked", () => {
    const r = render();
    expect(text(r)).not.toContain("어딘가");
    act(() => r.root.findByProps({ testID: "plan-missing-toggle" }).props.onPress());
    expect(text(r)).toContain("어딘가");
  });

  it("assembles only the still-selected places, with the source metadata", () => {
    const r = render();
    act(() => r.root.findByProps({ testID: "pick-케이블카" }).props.onPress());
    act(() => r.root.findByProps({ testID: "plan-assemble" }).props.onPress());

    expect(mutate).toHaveBeenCalledWith(
      {
        places: [imported.places[0]],
        days: 2,
        sourceKind: "youtube",
        sourceUrl: "https://youtu.be/x",
        sourceTitle: "통영 브이로그",
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it("disables the CTA when nothing is selected", () => {
    const r = render();
    act(() => r.root.findByProps({ testID: "pick-동피랑" }).props.onPress());
    act(() => r.root.findByProps({ testID: "pick-케이블카" }).props.onPress());

    expect(r.root.findByProps({ testID: "plan-assemble" }).props.disabled).toBe(true);
    expect(text(r)).toContain("장소를 골라 주세요");
  });
});
