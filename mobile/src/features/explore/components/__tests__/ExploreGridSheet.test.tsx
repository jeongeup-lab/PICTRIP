import renderer, { act } from "react-test-renderer";
import { ExploreGridSheet } from "@/features/explore/components/ExploreGridSheet";
import type { OverseasPost } from "@/features/explore/api";

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }),
}));

function post(id: number, countryCode: string, countryNameKo: string): OverseasPost {
  return {
    id,
    nameKo: `장소 ${id}`,
    countryCode,
    countryNameKo,
    descriptionKo: null,
    imageUrl: `https://upload.wikimedia.org/${id}.jpg`,
    imageAuthor: null,
    imageLicense: null,
    imageLicenseUrl: null,
    imageSourceUrl: `https://commons.wikimedia.org/${id}`,
  };
}

const POSTS: OverseasPost[] = [
  post(1, "JP", "일본"),
  post(2, "FR", "프랑스"),
  post(3, "IT", "이탈리아"),
  post(4, "US", "미국"),
  post(5, "DE", "독일"),
  post(6, "CN", "중국"),
];

function hosts(r: renderer.ReactTestRenderer, testID: string) {
  return r.root.findAllByProps({ testID }).filter((n) => typeof n.type === "string");
}

let tree: renderer.ReactTestRenderer | null = null;
let onPick: jest.Mock;
let onClose: jest.Mock;

afterEach(() => {
  act(() => tree?.unmount());
  tree = null;
  jest.clearAllMocks();
});

async function mount(posts: OverseasPost[] = POSTS) {
  onPick = jest.fn();
  onClose = jest.fn();
  await act(async () => {
    tree = renderer.create(
      <ExploreGridSheet posts={posts} onPick={onPick} onClose={onClose} onEndReached={jest.fn()} />,
    );
  });
  return tree!;
}

function press(r: renderer.ReactTestRenderer, testID: string, at = 0) {
  const target = r.root
    .findAllByProps({ testID })
    .filter((n) => typeof n.props.onPress === "function")[at];
  act(() => target.props.onPress());
}

describe("ExploreGridSheet", () => {
  it("renders a labelled tile per post", async () => {
    const r = await mount();
    expect(hosts(r, "explore-grid-tile").length).toBe(6);
  });

  it("offers only the continents present in the feed", async () => {
    const r = await mount();
    expect(hosts(r, "explore-continent-전체").length).toBe(1);
    expect(hosts(r, "explore-continent-유럽").length).toBe(1);
    expect(hosts(r, "explore-continent-아시아").length).toBe(1);
    expect(hosts(r, "explore-continent-아메리카").length).toBe(1);
    expect(hosts(r, "explore-continent-아프리카").length).toBe(0);
  });

  it("narrows the mosaic to the picked continent", async () => {
    const r = await mount();
    press(r, "explore-continent-유럽");
    expect(hosts(r, "explore-grid-tile").length).toBe(3);
  });

  it("reports the index in the unfiltered feed so the deck lands on the right post", async () => {
    const r = await mount();
    press(r, "explore-continent-아메리카");
    press(r, "explore-grid-tile");
    expect(onPick).toHaveBeenCalledWith(3);
  });

  it("goes back to every post when 전체 is picked again", async () => {
    const r = await mount();
    press(r, "explore-continent-아시아");
    expect(hosts(r, "explore-grid-tile").length).toBe(2);
    press(r, "explore-continent-전체");
    expect(hosts(r, "explore-grid-tile").length).toBe(6);
  });

  it("keeps posts whose country is not on the continent map under 전체", async () => {
    const r = await mount([post(1, "ZZ", "어딘가"), post(2, "JP", "일본")]);
    expect(hosts(r, "explore-grid-tile").length).toBe(2);
    expect(hosts(r, "explore-continent-아시아").length).toBe(1);
  });

  it("shows an empty note instead of a blank mosaic", async () => {
    const r = await mount([]);
    expect(hosts(r, "explore-grid-tile").length).toBe(0);
  });

  it("closes on the close button", async () => {
    const r = await mount();
    press(r, "explore-grid-close");
    expect(onClose).toHaveBeenCalled();
  });
});
