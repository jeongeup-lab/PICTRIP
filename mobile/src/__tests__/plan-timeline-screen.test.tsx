import renderer, { act } from "react-test-renderer";
import PlanTimelineScreen from "@/app/plan/[planId]";
import type { Plan, ResolvedPlace, ScheduleDay } from "@/features/plan/api";
import { useAlternatives, usePlan, usePlanEditMutation } from "@/features/plan/queries";

jest.mock("expo-router", () => ({
  router: { back: jest.fn(), push: jest.fn(), replace: jest.fn() },
  useLocalSearchParams: () => ({ planId: "Xq2" }),
}));
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: (props: { children?: unknown }) => props.children,
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/features/plan/components/PlanRouteMap", () => ({ PlanRouteMap: () => null }));
jest.mock("@/features/plan/queries", () => ({
  usePlan: jest.fn(),
  usePlanEditMutation: jest.fn(),
  useAlternatives: jest.fn(),
}));

const usePlanMock = usePlan as jest.Mock;
const useEditMock = usePlanEditMutation as jest.Mock;
const useAlternativesMock = useAlternatives as jest.Mock;

const place = (title: string): ResolvedPlace => ({
  extracted: {
    name: title,
    nameKo: null,
    placeType: "attraction",
    regionHint: null,
    tip: null,
    orderHint: null,
  },
  spot: {
    source: "kto",
    contentId: title,
    title,
    category: "관광지",
    address: "경상남도 통영시 도남동",
    lat: 34.8,
    lng: 128.4,
    imageUrl: null,
  },
  confidence: 1,
  status: "matched",
});

const day = (n: number, titles: string[]): ScheduleDay => ({
  day: n,
  regionLabel: "통영",
  slots: titles.map((t, i) => ({
    timeOfDay: "morning",
    place: place(t),
    travelMinutesFromPrev: i === 0 ? null : 15,
  })),
});

const plan = (over: Partial<Plan> = {}): Plan => ({
  planId: "Xq2",
  sourceTitle: "통영 당일 코스",
  sourceUrl: null,
  days: [day(1, ["동피랑", "케이블카"])],
  unplaced: [],
  ...over,
});

let mutate: jest.Mock;
let tree: renderer.ReactTestRenderer | null = null;

const render = () => {
  act(() => {
    tree = renderer.create(<PlanTimelineScreen />);
  });
  return tree!;
};

const text = (r: renderer.ReactTestRenderer) => JSON.stringify(r.toJSON());

beforeEach(() => {
  jest.clearAllMocks();
  mutate = jest.fn();
  useEditMock.mockReturnValue({ mutate, isPending: false });
  useAlternativesMock.mockReturnValue({ data: [], isLoading: false, isError: false });
  usePlanMock.mockReturnValue({ data: plan(), isLoading: false, isError: false, error: null });
});

afterEach(() => {
  act(() => tree?.unmount());
  tree = null;
});

describe("plan timeline screen", () => {
  it("shows the plan title, visit count and total travel time", () => {
    const body = text(render());
    expect(body).toContain("통영 당일 코스");
    expect(body).toContain("2곳");
    expect(body).toContain("약 15분");
  });

  it("hides the day chips for a same-day plan", () => {
    expect(text(render())).not.toContain("Day 1");
  });

  it("shows day chips once the plan spans multiple days", () => {
    usePlanMock.mockReturnValue({
      data: plan({ days: [day(1, ["동피랑"]), day(2, ["케이블카"])] }),
      isLoading: false,
      isError: false,
      error: null,
    });
    const body = text(render());
    expect(body).toContain("Day 1");
    expect(body).toContain("Day 2");
    expect(body).toContain("1박 2일");
  });

  it("removes a slot through the sheet using its day and index", () => {
    const r = render();
    act(() => r.root.findByProps({ testID: "slot-케이블카" }).props.onPress());
    act(() => r.root.findByProps({ testID: "slot-remove" }).props.onPress());

    expect(mutate).toHaveBeenCalledWith(
      { op: "remove", day: 1, slot: 1 },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it("replaces a slot with the chosen alternative's contentId", () => {
    useAlternativesMock.mockReturnValue({
      data: [
        {
          source: "kto",
          contentId: "999",
          title: "이순신공원",
          category: null,
          address: null,
          lat: null,
          lng: null,
          imageUrl: null,
        },
      ],
      isLoading: false,
      isError: false,
    });

    const r = render();
    act(() => r.root.findByProps({ testID: "slot-동피랑" }).props.onPress());
    act(() => r.root.findByProps({ testID: "slot-swap" }).props.onPress());
    act(() => r.root.findByProps({ testID: "alt-999" }).props.onPress());

    expect(mutate).toHaveBeenCalledWith(
      { op: "replace", day: 1, slot: 0, contentId: "999" },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it("names the places the backend could not fit into the schedule", () => {
    usePlanMock.mockReturnValue({
      data: plan({ unplaced: [place("소매물도")] }),
      isLoading: false,
      isError: false,
      error: null,
    });
    const body = text(render());
    expect(body).toContain("일정에 넣지 못한 ");
    expect(body).toContain("소매물도");
  });

  it("shows a code-derived message when the plan is gone", () => {
    const { AppError } = jest.requireActual("@/lib/app-error") as typeof import("@/lib/app-error");
    usePlanMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new AppError("PLAN_NOT_FOUND", "서버 문구", 404),
    });
    expect(text(render())).toContain("요청한 일정을 찾을 수 없어요");
  });
});
