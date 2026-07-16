import renderer, { act } from "react-test-renderer";
import { Image } from "react-native";
import { Image as ExpoImage } from "expo-image";
import { fullSizeSourceUri, RemoteImage } from "@/components/RemoteImage";

const images = (r: renderer.ReactTestRenderer) =>
  r.root.findAllByType(ExpoImage).filter((n) => n.props.onError);
const allImages = (r: renderer.ReactTestRenderer) => r.root.findAllByType(ExpoImage);

async function failAllRetries(r: renderer.ReactTestRenderer) {
  for (const delay of [900, 1800]) {
    await act(async () => {
      images(r)[0].props.onError();
    });
    await act(async () => {
      jest.advanceTimersByTime(delay);
    });
  }
  await act(async () => {
    images(r)[0].props.onError();
  });
}

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

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

  it("reads image dimensions from a web load event without nativeEvent.source", async () => {
    const onLoad = jest.fn();
    jest.spyOn(Image, "getSize").mockImplementation((_uri, success) => success(1200, 800));
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri="https://example.com/a.jpg" onLoad={onLoad} />);
    });
    await act(async () => {
      images(r!)[0].props.onLoad({});
    });
    expect(Image.getSize).toHaveBeenCalledWith(
      "https://example.com/a.jpg",
      expect.any(Function),
      expect.any(Function),
    );
    expect(onLoad).toHaveBeenCalledWith({
      uri: "https://example.com/a.jpg",
      width: 1200,
      height: 800,
    });
  });

  it("ignores a stale web dimension callback after the uri changes", async () => {
    const callbacks: ((width: number, height: number) => void)[] = [];
    const onLoad = jest.fn();
    jest.spyOn(Image, "getSize").mockImplementation((_uri, success) => {
      callbacks.push(success);
    });
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri="https://example.com/a.jpg" onLoad={onLoad} />);
    });
    await act(async () => {
      images(r!)[0].props.onLoad({});
      r!.update(<RemoteImage uri="https://example.com/b.jpg" onLoad={onLoad} />);
    });
    await act(async () => {
      images(r!)[0].props.onLoad({});
      callbacks[1](800, 1200);
      callbacks[0](1200, 800);
    });

    expect(onLoad).toHaveBeenCalledTimes(1);
    expect(onLoad).toHaveBeenCalledWith({
      uri: "https://example.com/b.jpg",
      width: 800,
      height: 1200,
    });
  });

  it("keeps the image mounted and retries after a transient error", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri="https://example.com/a.jpg" />);
    });
    await act(async () => {
      images(r!)[0].props.onError();
    });
    expect(images(r!)).toHaveLength(1);
    await act(async () => {
      jest.advanceTimersByTime(900);
    });
    expect(images(r!)).toHaveLength(1);
    expect(images(r!)[0].props.source.uri).toBe("https://example.com/a.jpg");
  });

  it("shows the placeholder once retries are exhausted", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri="https://example.com/a.jpg" />);
    });
    await failAllRetries(r!);
    expect(images(r!)).toHaveLength(0);
  });

  it("resets the failed state when the uri changes", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri="https://example.com/a.jpg" />);
    });
    await failAllRetries(r!);
    expect(images(r!)).toHaveLength(0);

    await act(async () => {
      r!.update(<RemoteImage uri="https://example.com/b.jpg" />);
    });
    const imgs = images(r!);
    expect(imgs).toHaveLength(1);
    expect(imgs[0].props.source.uri).toBe("https://example.com/b.jpg");
  });

  it("gives a new uri a fresh retry cycle after the previous uri exhausted retries", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri="https://example.com/a.jpg" />);
    });
    await failAllRetries(r!);
    expect(images(r!)).toHaveLength(0);

    await act(async () => {
      r!.update(<RemoteImage uri="https://example.com/b.jpg" />);
    });
    // A single error on the new uri must retry (stay mounted), not inherit the
    // previous uri's exhausted retry count and drop straight to the placeholder.
    await act(async () => {
      images(r!)[0].props.onError();
    });
    expect(images(r!)).toHaveLength(1);
    await act(async () => {
      jest.advanceTimersByTime(900);
    });
    expect(images(r!)[0].props.source.uri).toBe("https://example.com/b.jpg");
  });

  const KTO_HIRES = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg";
  const KTO_MID = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg";
  const PROXIED_KTO_HIRES =
    "https://img.pictrip.org/tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg";
  const PROXIED_KTO_MID =
    "https://img.pictrip.org/tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg";

  it("routes a KTO uri through the image proxy", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={KTO_HIRES} />);
    });
    expect(images(r!)[0].props.source.uri).toBe(PROXIED_KTO_HIRES);
  });

  it("degrades a proxied KTO uri to the direct url on error, without delay", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={KTO_HIRES} />);
    });
    expect(images(r!)[0].props.source.uri).toBe(PROXIED_KTO_HIRES);
    // Proxy outage escape hatch — the Worker itself already serves the mid-size
    // when a dead original 404s, so client degrade goes proxy → direct instead.
    await act(async () => {
      images(r!)[0].props.onError();
    });
    const imgs = images(r!);
    expect(imgs).toHaveLength(1);
    expect(imgs[0].props.source.uri).toBe(KTO_HIRES);
  });

  it("paints a blurred KTO mid-size preview behind the hi-res original, proxied", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={KTO_HIRES} />);
    });
    const preview = allImages(r!).find((n) => !n.props.onError);
    expect(preview?.props.source.uri).toBe(PROXIED_KTO_MID);
    expect(preview?.props.blurRadius).toBe(6);
    expect(images(r!)[0].props.source.uri).toBe(PROXIED_KTO_HIRES);
  });

  it("keeps a direct (unproxied) preview after degrading to the direct original", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={KTO_HIRES} />);
    });
    await act(async () => {
      images(r!)[0].props.onError();
    });
    const preview = allImages(r!).find((n) => !n.props.onError);
    expect(preview?.props.source.uri).toBe(KTO_MID);
    expect(images(r!)[0].props.source.uri).toBe(KTO_HIRES);
  });

  it("shows no preview for a non-KTO uri", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri="https://example.com/a.jpg" />);
    });
    expect(allImages(r!)).toHaveLength(1);
  });

  it("does not degrade a non-KTO url that merely contains _image1_1", async () => {
    // Foreign host with the same token in its path must keep normal same-uri retry.
    const ext = "https://cdn.example.com/photos/x_image1_1.jpg";
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={ext} />);
    });
    await act(async () => {
      images(r!)[0].props.onError();
    });
    // Retries the same uri (mounted), does NOT rewrite to _image2_1.
    expect(images(r!)).toHaveLength(1);
    await act(async () => {
      jest.advanceTimersByTime(900);
    });
    expect(images(r!)[0].props.source.uri).toBe(ext);
  });

  it("does not carry a prior image's degrade onto a newly-assigned KTO uri", async () => {
    const A_HIRES = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg";
    const B_HIRES = "https://tong.visitkorea.or.kr/cms/resource/12/1112223_image1_1.jpg";
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={A_HIRES} />);
    });
    // A's proxied request errors → degraded to A's direct url.
    await act(async () => {
      images(r!)[0].props.onError();
    });
    expect(images(r!)[0].props.source.uri).toBe(A_HIRES);
    // Switch to B: its first request must be B's proxied form, not a degraded one.
    await act(async () => {
      r!.update(<RemoteImage uri={B_HIRES} />);
    });
    expect(images(r!)[0].props.source.uri).toBe(
      B_HIRES.replace(
        "https://tong.visitkorea.or.kr",
        "https://img.pictrip.org/tong.visitkorea.or.kr",
      ),
    );
  });

  it("degrades only once, then the direct url follows normal retry then placeholder", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={KTO_HIRES} />);
    });
    await act(async () => {
      images(r!)[0].props.onError();
    });
    expect(images(r!)[0].props.source.uri).toBe(KTO_HIRES);
    // From here the direct url behaves like any uri: retry, retry, then give up.
    await failAllRetries(r!);
    expect(images(r!)).toHaveLength(0);
  });

  it("midSize renders the proxied KTO mid-size as the main image with no blur preview", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={KTO_HIRES} midSize />);
    });
    expect(allImages(r!)).toHaveLength(1);
    expect(images(r!)[0].props.source.uri).toBe(PROXIED_KTO_MID);
  });

  it("midSize on a non-KTO uri leaves it untouched", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri="https://example.com/a.jpg" midSize />);
    });
    expect(allImages(r!)).toHaveLength(1);
    expect(images(r!)[0].props.source.uri).toBe("https://example.com/a.jpg");
  });

  const COMMONS_THUMB =
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Kyoto.jpg/1200px-Kyoto.jpg";
  const COMMONS_FILEPATH =
    "https://commons.wikimedia.org/wiki/Special:FilePath/Kyoto.jpg?width=1200";

  it("routes a Commons uri through the image proxy", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={COMMONS_THUMB} />);
    });
    expect(images(r!)[0].props.source.uri).toBe(
      "https://img.pictrip.org/upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Kyoto.jpg/1200px-Kyoto.jpg",
    );
  });

  it("commonsWidth rewrites a direct upload.wikimedia thumb width, proxied", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={COMMONS_THUMB} commonsWidth={320} />);
    });
    expect(images(r!)[0].props.source.uri).toBe(
      "https://img.pictrip.org/upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Kyoto.jpg/320px-Kyoto.jpg",
    );
  });

  it("commonsWidth rewrites a Special:FilePath width param, proxied", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={COMMONS_FILEPATH} commonsWidth={480} />);
    });
    expect(images(r!)[0].props.source.uri).toBe(
      "https://img.pictrip.org/commons.wikimedia.org/wiki/Special:FilePath/Kyoto.jpg?width=480",
    );
  });

  it("commonsWidth leaves a non-wikimedia uri's width untouched (still proxied)", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={KTO_HIRES} commonsWidth={320} />);
    });
    expect(images(r!)[0].props.source.uri).toBe(PROXIED_KTO_HIRES);
  });

  it("does not proxy a uri outside the proxyable hosts", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri="https://example.com/a.jpg" />);
    });
    expect(images(r!)[0].props.source.uri).toBe("https://example.com/a.jpg");
  });

  it("fullSizeSourceUri proxies a KTO original untouched and skips foreign hosts", () => {
    expect(fullSizeSourceUri(KTO_HIRES)).toBe(PROXIED_KTO_HIRES);
    expect(fullSizeSourceUri("https://example.com/a.jpg")).toBe("https://example.com/a.jpg");
  });

  it("degrades a proxied Commons uri to the direct url on error, keeping the width", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={COMMONS_THUMB} commonsWidth={320} />);
    });
    await act(async () => {
      images(r!)[0].props.onError();
    });
    const imgs = images(r!);
    expect(imgs).toHaveLength(1);
    expect(imgs[0].props.source.uri).toBe(
      "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Kyoto.jpg/320px-Kyoto.jpg",
    );
  });

  it("after degrading to the direct Commons url, follows normal retry then placeholder", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={COMMONS_THUMB} />);
    });
    await act(async () => {
      images(r!)[0].props.onError();
    });
    expect(images(r!)[0].props.source.uri).toBe(COMMONS_THUMB);
    await failAllRetries(r!);
    expect(images(r!)).toHaveLength(0);
  });

  it("retries again after an A→B→A round-trip back to a previously-failed uri", async () => {
    const A = "https://example.com/a.jpg";
    const B = "https://example.com/b.jpg";
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={A} />);
    });
    await failAllRetries(r!);
    expect(images(r!)).toHaveLength(0);

    await act(async () => {
      r!.update(<RemoteImage uri={B} />);
    });
    await act(async () => {
      r!.update(<RemoteImage uri={A} />);
    });
    // Back on A: a single error must retry, not reuse A's earlier exhausted count.
    await act(async () => {
      images(r!)[0].props.onError();
    });
    expect(images(r!)).toHaveLength(1);
    expect(images(r!)[0].props.source.uri).toBe(A);
  });
});
