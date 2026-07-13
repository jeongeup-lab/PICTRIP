import renderer, { act } from "react-test-renderer";
import { Image, StyleSheet, View } from "react-native";
import { StoryImage } from "@/features/channels/components/StoryImage";

const layout = async (r: renderer.ReactTestRenderer, width: number, height: number) => {
  await act(async () => {
    r.root.findAllByType(View)[0].props.onLayout({ nativeEvent: { layout: { width, height } } });
  });
};

afterEach(() => jest.restoreAllMocks());

describe("StoryImage", () => {
  it("letterboxes the image to its watermark-cropped aspect ratio", async () => {
    jest.spyOn(Image, "getSize").mockImplementation((_uri, ok) => ok(940, 626));
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<StoryImage uri="https://tong.visitkorea.or.kr/a.jpg" />);
    });
    await layout(r!, 390, 780);
    const frame = r!.root.findByProps({ testID: "story-image-frame" });
    const style = StyleSheet.flatten(frame.props.style);
    expect(style.width).toBe(390);
    expect(Math.round(style.height as number)).toBe(229);
    expect(style.top).toBeGreaterThan(0);
  });

  it("shows only the blurred backdrop until dimensions resolve", async () => {
    jest.spyOn(Image, "getSize").mockImplementation(() => {});
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<StoryImage uri="https://tong.visitkorea.or.kr/a.jpg" />);
    });
    await layout(r!, 390, 780);
    expect(r!.root.findAllByProps({ testID: "story-image-frame" })).toHaveLength(0);
    expect(r!.root.findAllByType(Image).length).toBeGreaterThan(0);
  });

  it("falls back to a plain full-bleed image when sizing fails", async () => {
    jest.spyOn(Image, "getSize").mockImplementation((_uri, _ok, fail) => fail?.(new Error("nope")));
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<StoryImage uri="https://tong.visitkorea.or.kr/a.jpg" />);
    });
    expect(r!.root.findAllByProps({ testID: "story-image-frame" })).toHaveLength(0);
    expect(r!.root.findAllByType(Image)).toHaveLength(1);
  });
});
