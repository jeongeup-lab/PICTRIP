import renderer, { act } from "react-test-renderer";
import { Image, StyleSheet, View } from "react-native";
import { FramedImage } from "@/components/FramedImage";

const KTO_HIRES = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg";
const KTO_MID = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg";

const images = (r: renderer.ReactTestRenderer) => r.root.findAllByType(Image);

const layout = async (r: renderer.ReactTestRenderer, width: number, height: number) => {
  await act(async () => {
    r.root.findAllByType(View)[0].props.onLayout({ nativeEvent: { layout: { width, height } } });
  });
};

const load = async (r: renderer.ReactTestRenderer, uri: string, width: number, height: number) => {
  await act(async () => {
    images(r)[0].props.onLoad({ nativeEvent: { source: { uri, width, height } } });
  });
};

beforeEach(() => jest.clearAllMocks());
afterEach(() => jest.restoreAllMocks());

describe("FramedImage", () => {
  it("letterboxes a loaded high-resolution image without Image.getSize", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<FramedImage uri={KTO_HIRES} />);
    });
    await layout(r!, 390, 780);
    expect(Image.getSize).not.toHaveBeenCalled();
    await load(r!, KTO_HIRES, 940, 626);
    const frame = r!.root.findByProps({ testID: "framed-image-frame" });
    const style = StyleSheet.flatten(frame.props.style);
    expect(style.width).toBe(390);
    expect(Math.round(style.height as number)).toBe(229);
    expect(style.top).toBeGreaterThan(0);
    expect(images(r!).map((image) => image.props.source.uri)).toEqual([KTO_HIRES, KTO_HIRES]);
  });

  it("shows only the blurred backdrop until its load dimensions resolve", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<FramedImage uri={KTO_HIRES} />);
    });
    await layout(r!, 390, 780);
    expect(r!.root.findAllByProps({ testID: "framed-image-frame" })).toHaveLength(0);
    expect(images(r!)).toHaveLength(1);
    expect(Image.getSize).not.toHaveBeenCalled();
  });

  it("renders the sharp frame from react-native-web load dimensions", async () => {
    jest.spyOn(Image, "getSize").mockImplementation((_uri, success) => success(940, 626));
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<FramedImage uri={KTO_HIRES} />);
    });
    await layout(r!, 390, 780);
    await act(async () => {
      images(r!)[0].props.onLoad({
        nativeEvent: {},
      });
    });
    expect(Image.getSize).toHaveBeenCalledWith(
      KTO_HIRES,
      expect.any(Function),
      expect.any(Function),
    );
    expect(r!.root.findByProps({ testID: "framed-image-frame" })).toBeTruthy();
    expect(images(r!)).toHaveLength(2);
  });

  it("keeps the backdrop load callback stable after measuring the image", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<FramedImage uri={KTO_HIRES} />);
    });
    const firstOnLoad = images(r!)[0].props.onLoad;
    const firstSource = images(r!)[0].props.source;
    await layout(r!, 390, 780);
    expect(images(r!)[0].props.onLoad).toBe(firstOnLoad);
    expect(images(r!)[0].props.source).toBe(firstSource);
    await load(r!, KTO_HIRES, 940, 626);
    expect(images(r!)[0].props.onLoad).toBe(firstOnLoad);
    expect(images(r!)[0].props.source).toBe(firstSource);
  });

  it("uses the successful mid-size fallback for both backdrop and frame", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<FramedImage uri={KTO_HIRES} />);
    });
    await layout(r!, 390, 780);
    await act(async () => {
      images(r!)[0].props.onError();
    });
    expect(images(r!)).toHaveLength(1);
    expect(images(r!)[0].props.source.uri).toBe(KTO_MID);
    await load(r!, KTO_MID, 940, 626);
    expect(r!.root.findByProps({ testID: "framed-image-frame" })).toBeTruthy();
    expect(images(r!).map((image) => image.props.source.uri)).toEqual([KTO_MID, KTO_MID]);
    expect(Image.getSize).not.toHaveBeenCalled();
  });
});
