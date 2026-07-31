import renderer, { act } from "react-test-renderer";
import { QueryClientProvider } from "@tanstack/react-query";
import { getSpot } from "@/features/spots/api";
import { prefetchSpot, useSpot } from "@/features/spots/queries";
import { queryClient } from "@/lib/query-client";
import type { SpotDetail } from "@/lib/api-types";

jest.mock("@/features/spots/api", () => ({
  getSpot: jest.fn(),
  getNearby: jest.fn(),
}));

const detail = (detailStatus: SpotDetail["detailStatus"]): SpotDetail => ({
  contentId: "777",
  title: "관광지",
  firstImageUrl: "https://tong.visitkorea.or.kr/cms/a_image2_1.jpg",
  addr1: "서울",
  addr2: null,
  mapx: 127,
  mapy: 37.5,
  overview: detailStatus === "fresh" ? "상세 설명" : null,
  homepage: null,
  tel: null,
  category: "명소",
  regionName: "서울",
  sigunguName: null,
  detailStatus,
  images: [],
  intro: null,
});

describe("spot detail seed", () => {
  let tree: renderer.ReactTestRenderer | undefined;

  beforeEach(() => {
    tree = undefined;
    queryClient.clear();
    (getSpot as jest.Mock).mockReset();
  });

  afterEach(async () => {
    await act(async () => {
      tree?.unmount();
    });
    queryClient.clear();
  });

  it("keeps the card image while pending detail data replaces the placeholder", async () => {
    let resolveRequest: ((value: SpotDetail) => void) | undefined;
    (getSpot as jest.Mock).mockImplementation(
      () =>
        new Promise<SpotDetail>((resolve) => {
          resolveRequest = resolve;
        }),
    );
    let result: ReturnType<typeof useSpot> | undefined;
    const seed = {
      contentId: "777",
      title: "관광지",
      imageUrl: "https://tong.visitkorea.or.kr/cms/a_image1_1.jpg",
    };

    function Harness() {
      result = useSpot("777", seed);
      return null;
    }

    await act(async () => {
      tree = renderer.create(
        <QueryClientProvider client={queryClient}>
          <Harness />
        </QueryClientProvider>,
      );
    });

    expect(result?.data?.detailStatus).toBe("placeholder");
    expect(result?.data?.firstImageUrl).toBe(seed.imageUrl);

    await act(async () => {
      queryClient.setQueryData(["spot", "777"], detail("pending"));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(result?.data?.detailStatus).toBe("pending");
    expect(result?.data?.firstImageUrl).toBe(seed.imageUrl);

    await act(async () => {
      resolveRequest?.(detail("fresh"));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  });

  it("uses a prefetched card seed during its navigation window", async () => {
    (getSpot as jest.Mock).mockResolvedValue(detail("fresh"));
    const seed = {
      contentId: "777",
      title: "관광지",
      imageUrl: "https://tong.visitkorea.or.kr/cms/a_image1_1.jpg",
    };

    await act(async () => {
      prefetchSpot(seed);
      await Promise.resolve();
    });

    let result: ReturnType<typeof useSpot> | undefined;
    function Harness() {
      result = useSpot("777");
      return null;
    }

    await act(async () => {
      tree = renderer.create(
        <QueryClientProvider client={queryClient}>
          <Harness />
        </QueryClientProvider>,
      );
      await Promise.resolve();
    });

    expect(result?.data?.detailStatus).toBe("fresh");
    expect(result?.data?.firstImageUrl).toBe(seed.imageUrl);
  });

  it("ignores an unconsumed card seed after its navigation window expires", async () => {
    const now = jest.spyOn(Date, "now").mockReturnValue(1_000);
    (getSpot as jest.Mock).mockResolvedValue(detail("fresh"));
    prefetchSpot({
      contentId: "777",
      title: "관광지",
      imageUrl: "https://tong.visitkorea.or.kr/cms/old_image1_1.jpg",
    });
    await act(async () => {
      await Promise.resolve();
    });
    now.mockReturnValue(31_001);

    let result: ReturnType<typeof useSpot> | undefined;
    function Harness() {
      result = useSpot("777");
      return null;
    }

    await act(async () => {
      tree = renderer.create(
        <QueryClientProvider client={queryClient}>
          <Harness />
        </QueryClientProvider>,
      );
    });

    expect(result?.data?.firstImageUrl).toBe("https://tong.visitkorea.or.kr/cms/a_image2_1.jpg");
    now.mockRestore();
  });
});
