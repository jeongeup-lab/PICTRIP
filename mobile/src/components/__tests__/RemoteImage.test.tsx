import renderer, { act } from "react-test-renderer";
import { Image } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";

const images = (r: renderer.ReactTestRenderer) => r.root.findAllByType(Image);

describe("RemoteImage", () => {
  it("renders the image for a valid uri", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri="https://example.com/a.jpg" />);
    });
    const imgs = images(r!);
    expect(imgs).toHaveLength(1);
    expect(imgs[0].props.source.uri).toBe("https://example.com/a.jpg");
  });

  it("shows the placeholder after the image errors", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri="https://example.com/a.jpg" />);
    });
    await act(async () => {
      images(r!)[0].props.onError();
    });
    expect(images(r!)).toHaveLength(0);
  });

  it("resets the failed state when the uri changes", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri="https://example.com/a.jpg" />);
    });
    await act(async () => {
      images(r!)[0].props.onError();
    });
    expect(images(r!)).toHaveLength(0);

    await act(async () => {
      r!.update(<RemoteImage uri="https://example.com/b.jpg" />);
    });
    const imgs = images(r!);
    expect(imgs).toHaveLength(1);
    expect(imgs[0].props.source.uri).toBe("https://example.com/b.jpg");
  });
});
