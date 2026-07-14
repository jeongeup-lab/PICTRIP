import renderer, { act } from "react-test-renderer";
import { Image } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";

const images = (r: renderer.ReactTestRenderer) => r.root.findAllByType(Image);

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

  it("degrades a KTO _image1_1 original to _image2_1 on error, without delay", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={KTO_HIRES} />);
    });
    expect(images(r!)[0].props.source.uri).toBe(KTO_HIRES);
    // Original 404s on ~20% of images → swap to the mid-size immediately (no backoff timer).
    await act(async () => {
      images(r!)[0].props.onError();
    });
    const imgs = images(r!);
    expect(imgs).toHaveLength(1);
    expect(imgs[0].props.source.uri).toBe(KTO_MID);
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
    // A's original 404s → degraded to A's mid-size.
    await act(async () => {
      images(r!)[0].props.onError();
    });
    expect(images(r!)[0].props.source.uri).toBe(A_HIRES.replace("_image1_1", "_image2_1"));
    // Switch to B: its first request must be B's original, not B's mid-size.
    await act(async () => {
      r!.update(<RemoteImage uri={B_HIRES} />);
    });
    expect(images(r!)[0].props.source.uri).toBe(B_HIRES);
  });

  it("degrades only once, then the mid-size follows normal retry then placeholder", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<RemoteImage uri={KTO_HIRES} />);
    });
    await act(async () => {
      images(r!)[0].props.onError();
    });
    expect(images(r!)[0].props.source.uri).toBe(KTO_MID);
    // From here the mid-size behaves like any uri: retry, retry, then give up.
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
