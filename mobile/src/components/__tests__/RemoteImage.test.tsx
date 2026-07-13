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
});
