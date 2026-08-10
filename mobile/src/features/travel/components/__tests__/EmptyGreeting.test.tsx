import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import {
  EmptyGreeting,
  GREETING_LINE1,
  GREETING_LINE2,
  HERO_LABEL,
  moodImageUri,
} from "@/features/travel/components/EmptyGreeting";
import type { MoodImage } from "@/features/travel/api";

const MOOD_IMAGES: MoodImage[] = [
  { code: "sea", imageUrl: "https://img/sea.jpg" },
  { code: "street", imageUrl: "https://img/street.jpg" },
  { code: "mountain", imageUrl: "https://img/mountain.jpg" },
];

function mount(props: Partial<React.ComponentProps<typeof EmptyGreeting>> = {}) {
  const onPickPhoto = jest.fn();
  let tree!: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<EmptyGreeting onPickPhoto={onPickPhoto} {...props} />);
  });
  return { tree, onPickPhoto };
}

function byId(tree: renderer.ReactTestRenderer, id: string) {
  return tree.root.findAll((node) => node.props?.testID === id, { deep: true });
}

function texts(tree: renderer.ReactTestRenderer): string[] {
  return tree.root.findAllByType(Text).flatMap((node) => {
    const children = node.props.children;
    return typeof children === "string" ? [children] : [];
  });
}

describe("EmptyGreeting", () => {
  it("헤드라인 두 줄을 보여준다", () => {
    const { tree } = mount();

    expect(texts(tree)).toContain(GREETING_LINE1);
    expect(texts(tree)).toContain(GREETING_LINE2);
  });

  it("사진 진입점은 히어로 하나뿐이다", () => {
    const { tree } = mount();

    const labelled = tree.root.findAll((node) => node.props?.accessibilityLabel === HERO_LABEL, {
      deep: false,
    });
    expect(labelled).toHaveLength(1);
  });

  it("히어로를 누르면 사진 선택으로 넘긴다", () => {
    const { tree, onPickPhoto } = mount();

    act(() => byId(tree, "travel-photo-hero")[0].props.onPress());

    expect(onPickPhoto).toHaveBeenCalledTimes(1);
  });

  it("무드 이미지가 오면 콜라주 세 장을 깐다", () => {
    const { tree } = mount({ moodImages: MOOD_IMAGES });

    expect(byId(tree, "travel-collage-0").length).toBeGreaterThan(0);
    expect(byId(tree, "travel-collage-2").length).toBeGreaterThan(0);
  });

  it("무드 이미지가 없어도 히어로는 그려진다", () => {
    const { tree } = mount();

    expect(byId(tree, "travel-collage-0")).toHaveLength(0);
    expect(byId(tree, "travel-photo-hero").length).toBeGreaterThan(0);
  });
});

describe("moodImageUri", () => {
  it("코드가 맞는 이미지를 고른다", () => {
    expect(moodImageUri(MOOD_IMAGES, "street")).toBe("https://img/street.jpg");
  });

  it("없으면 null", () => {
    expect(moodImageUri([], "sea")).toBeNull();
    expect(moodImageUri(undefined, "sea")).toBeNull();
  });
});
