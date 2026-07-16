import { describe, expect, it } from "vitest";
import { verifyT1Signature } from "./sign";
import { ktoFallbackUpstream, resolveT1, resolveUpstream } from "./upstream";

const resolve = (path: string) => resolveUpstream(new URL(`https://img.pictrip.org${path}`));

describe("resolveUpstream", () => {
  it("maps an upload.wikimedia.org thumb path to the upstream url", () => {
    expect(
      resolve("/upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Foo.jpg/480px-Foo.jpg"),
    ).toBe("https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Foo.jpg/480px-Foo.jpg");
  });

  it("maps a commons.wikimedia.org Special:FilePath url with query", () => {
    expect(resolve("/commons.wikimedia.org/wiki/Special:FilePath/Foo.jpg?width=480")).toBe(
      "https://commons.wikimedia.org/wiki/Special:FilePath/Foo.jpg?width=480",
    );
  });

  it("keeps percent-encoded characters intact", () => {
    expect(
      resolve("/upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Caf%C3%A9.jpg/480px-Caf%C3%A9.jpg"),
    ).toBe("https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Caf%C3%A9.jpg/480px-Caf%C3%A9.jpg");
  });

  it("maps a tong.visitkorea.or.kr KTO path to the upstream url", () => {
    expect(resolve("/tong.visitkorea.or.kr/cms/resource/13/3564113_image1_1.jpg")).toBe(
      "https://tong.visitkorea.or.kr/cms/resource/13/3564113_image1_1.jpg",
    );
  });

  it("rejects hosts outside the allowlist", () => {
    expect(resolve("/evil.example.com/wikipedia/commons/foo.jpg")).toBeNull();
    expect(resolve("/korean.visitkorea.or.kr/foo.jpg")).toBeNull();
  });

  it("rejects an empty upstream path", () => {
    expect(resolve("/upload.wikimedia.org")).toBeNull();
    expect(resolve("/upload.wikimedia.org/")).toBeNull();
    expect(resolve("/")).toBeNull();
  });

  it("cannot escape the allowlisted host via path traversal", () => {
    expect(resolve("/upload.wikimedia.org/../secret")).toBeNull();
    expect(resolve("/upload.wikimedia.org/%2e%2e/foo.jpg")).toBeNull();
    expect(resolve("/upload.wikimedia.org/wikipedia/%2e%2e/foo.jpg")).toBe(
      "https://upload.wikimedia.org/foo.jpg",
    );
  });
});

describe("ktoFallbackUpstream", () => {
  it("rewrites a dead KTO hi-res original to the mid-size variant", () => {
    expect(
      ktoFallbackUpstream("https://tong.visitkorea.or.kr/cms/resource/68/3336968_image1_1.jpg"),
    ).toBe("https://tong.visitkorea.or.kr/cms/resource/68/3336968_image2_1.jpg");
  });

  it("returns null for non-KTO hosts even with the hi-res marker", () => {
    expect(ktoFallbackUpstream("https://upload.wikimedia.org/foo_image1_1.jpg")).toBeNull();
  });

  it("returns null for KTO paths without the hi-res marker", () => {
    expect(
      ktoFallbackUpstream("https://tong.visitkorea.or.kr/cms/resource/68/3336968_image2_1.jpg"),
    ).toBeNull();
  });
});

const SIG = "028d9555b9ae4773de10afb7337628f25fc51e2fd2351dd253b563e25288b6e3";
const T1_PATH = `/t1/1080/${SIG}/tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg`;
const resolveT1Path = (path: string) => resolveT1(new URL(`https://img.pictrip.org${path}`));

describe("resolveT1", () => {
  it("parses width, signature and upstream from a signed transform path", () => {
    expect(resolveT1Path(T1_PATH)).toEqual({
      upstream: "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg",
      width: 1080,
      sig: SIG,
      payload: "1080/tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg",
    });
  });

  it("rejects non-KTO hosts even with a well-formed signature", () => {
    expect(resolveT1Path(`/t1/1080/${SIG}/upload.wikimedia.org/foo.jpg`)).toBeNull();
  });

  it("rejects out-of-range widths and malformed signatures", () => {
    expect(resolveT1Path(`/t1/9999/${SIG}/tong.visitkorea.or.kr/x.jpg`)).toBeNull();
    expect(resolveT1Path(`/t1/8/${SIG}/tong.visitkorea.or.kr/x.jpg`)).toBeNull();
    expect(resolveT1Path("/t1/1080/nothex/tong.visitkorea.or.kr/x.jpg")).toBeNull();
    expect(resolveT1Path(`/t1/1080/${SIG}`)).toBeNull();
  });
});

describe("verifyT1Signature", () => {
  const payload = "1080/tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg";

  it("accepts the backend-minted signature", async () => {
    expect(await verifyT1Signature("s3cret", payload, SIG)).toBe(true);
  });

  it("rejects a tampered payload or wrong secret", async () => {
    expect(await verifyT1Signature("s3cret", payload.replace("1080", "1620"), SIG)).toBe(false);
    expect(await verifyT1Signature("other", payload, SIG)).toBe(false);
    expect(await verifyT1Signature("s3cret", payload, `${SIG.slice(0, 63)}0`)).toBe(false);
  });
});
