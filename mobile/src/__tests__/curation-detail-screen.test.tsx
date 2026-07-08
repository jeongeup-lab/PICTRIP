import renderer, { act } from "react-test-renderer";
import CurationScreen from "@/app/curations/[slug]";
import { useCuration } from "@/features/curation/queries";
import { AppError } from "@/lib/app-error";
import type { CurationDetail } from "@/lib/api-types";

jest.mock("expo-router", () => ({
  router: { back: jest.fn(), push: jest.fn() },
  useLocalSearchParams: () => ({ slug: "jeju" }),
}));
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: (props: { children?: unknown }) => props.children,
}));
jest.mock("@/features/curation/queries", () => ({ useCuration: jest.fn() }));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));

const useCurationMock = useCuration as jest.Mock;
const { router } = jest.requireMock("expo-router") as {
  router: { back: jest.Mock; push: jest.Mock };
};

const detail = (overrides: Partial<CurationDetail> = {}): CurationDetail => ({
  id: 1,
  type: "region",
  slug: "jeju",
  title: "제주, 매일 가도\n새로운 섬",
  lead: "바다도 골목도, 전부 제주",
  intro: "오름과 해변, 골목 카페까지",
  coverUrl: "https://example.com/cover.jpg",
  spots: [],
  ...overrides,
});

const queryState = (overrides: Record<string, unknown>) => ({
  data: undefined,
  isLoading: false,
  isError: false,
  error: null,
  refetch: jest.fn(),
  ...overrides,
});

describe("CurationScreen error states", () => {
  let tree: renderer.ReactTestRenderer | null = null;

  afterEach(() => {
    act(() => tree?.unmount());
    tree = null;
    jest.clearAllMocks();
  });

  it("shows the not-found copy and a back action on RESOURCE_NOT_FOUND", async () => {
    useCurationMock.mockReturnValue(
      queryState({
        isError: true,
        error: new AppError("RESOURCE_NOT_FOUND", "요청한 리소스를 찾을 수 없습니다.", 404),
      }),
    );
    await act(async () => {
      tree = renderer.create(<CurationScreen />);
    });

    expect(JSON.stringify(tree!.toJSON())).toContain("큐레이션을 찾을 수 없어요");
    await act(async () => {
      tree!.root.findByProps({ label: "뒤로가기" }).props.onPress();
    });
    expect(router.back).toHaveBeenCalled();
  });

  it("shows a retry action on non-404 errors and refetches on press", async () => {
    const refetch = jest.fn();
    useCurationMock.mockReturnValue(
      queryState({
        isError: true,
        error: new AppError("INTERNAL_ERROR", "서버 오류", 500),
        refetch,
      }),
    );
    await act(async () => {
      tree = renderer.create(<CurationScreen />);
    });

    const json = JSON.stringify(tree!.toJSON());
    expect(json).toContain("큐레이션을 불러오지 못했어요");
    expect(json).not.toContain("큐레이션을 찾을 수 없어요");
    await act(async () => {
      tree!.root.findByProps({ label: "다시 시도" }).props.onPress();
    });
    expect(refetch).toHaveBeenCalled();
  });

  it("shows the soft empty notice when the curation has zero spots", async () => {
    useCurationMock.mockReturnValue(queryState({ data: detail({ spots: [] }) }));
    await act(async () => {
      tree = renderer.create(<CurationScreen />);
    });

    expect(JSON.stringify(tree!.toJSON())).toContain("곧 새로운 스팟을 준비할게요");
  });
});
