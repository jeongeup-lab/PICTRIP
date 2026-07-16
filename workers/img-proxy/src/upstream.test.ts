import { describe, expect, it } from "vitest";
import { resolveUpstream } from "./upstream";

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

  it("rejects hosts outside the allowlist", () => {
    expect(resolve("/evil.example.com/wikipedia/commons/foo.jpg")).toBeNull();
    expect(resolve("/tong.visitkorea.or.kr/cms_data/foo.jpg")).toBeNull();
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
