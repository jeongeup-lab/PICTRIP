import renderer, { act } from "react-test-renderer";
import { SpotGridCard } from "@/features/home/components/SpotGridCard";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import type { HomeSpotCard } from "@/features/home/api";

jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({ useSaveOptimistic: jest.fn() }));

const mockSave = useSaveOptimistic as jest.Mock;

const card = (over: Partial<HomeSpotCard> = {}): HomeSpotCard => ({
  contentId: "c1",
  title: "롯데시네마 월드타워",
  regionLabel: "서울특별시 송파구",
  imageUrl: "https://tong.visitkorea.or.kr/cms/a_image1_1.jpg",
  rank: null,
  dist: null,
  category: null,
  tag: null,
  anchorTitle: null,
  lat: null,
  lng: null,
  ...over,
});

let toggle: jest.Mock;

beforeEach(() => {
  toggle = jest.fn(async () => true);
  mockSave.mockReturnValue({ saved: false, toggle });
});

afterEach(() => jest.clearAllMocks());

const saveButton = (r: renderer.ReactTestRenderer) =>
  r.root
    .findAllByProps({ testID: "home-save-button" })
    .filter((n) => typeof n.props.onPress === "function")[0];

async function mount(props: Partial<Parameters<typeof SpotGridCard>[0]> = {}) {
  let tree: renderer.ReactTestRenderer;
  await act(async () => {
    tree = renderer.create(
      <SpotGridCard
        card={card()}
        width={180}
        subtitle="여기서 4.7km"
        onPress={() => {}}
        {...props}
      />,
    );
  });
  return tree!;
}

const json = (r: renderer.ReactTestRenderer) => JSON.stringify(r.toJSON());

describe("SpotGridCard", () => {
  it("shows the rank numeral and hashtag for a ranked card", async () => {
    const r = await mount({ card: card({ rank: 1, tag: "전시관" }) });
    expect(r.root.findByProps({ testID: "home-card-rank" }).props.children).toBe(1);
    expect(json(r)).toContain("전시관");
  });

  it("hides the rank block for an unranked recommendation card", async () => {
    const r = await mount({ card: card({ tag: "카페" }) });
    expect(r.root.findAllByProps({ testID: "home-card-rank" })).toHaveLength(0);
    expect(json(r)).not.toContain("#카페");
  });

  it("shows the title and subtitle in the footer", async () => {
    const r = await mount({ subtitle: "중식당 · 724m" });
    expect(json(r)).toContain("롯데시네마 월드타워");
    expect(json(r)).toContain("중식당 · 724m");
  });

  it("tapping the scrap button toggles the save without opening the spot", async () => {
    const onPress = jest.fn();
    const r = await mount({ onPress });
    await act(async () => {
      saveButton(r).props.onPress();
    });
    expect(toggle).toHaveBeenCalled();
    expect(onPress).not.toHaveBeenCalled();
  });

  it("fills the bookmark once the spot is saved", async () => {
    mockSave.mockReturnValue({ saved: true, toggle });
    const r = await mount();
    expect(saveButton(r).findAllByProps({ name: "bookmark-fill" }).length).toBeGreaterThan(0);
  });
});
