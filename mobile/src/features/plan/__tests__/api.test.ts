import type { InternalAxiosRequestConfig } from "axios";
import { api } from "@/lib/api-client";
import { matchPhoto, importContent } from "@/features/plan/api";

const photo = { uri: "file:///a.jpg", name: "a.jpg", type: "image/jpeg" };

let seen: InternalAxiosRequestConfig | null = null;
const originalAdapter = api.defaults.adapter;

const contentType = (config: InternalAxiosRequestConfig | null) =>
  config?.headers["Content-Type"] ?? config?.headers["content-type"];

beforeEach(() => {
  seen = null;
  api.defaults.adapter = (config) => {
    seen = config;
    return Promise.resolve({
      data: { data: { matches: [] }, error: null, meta: {} },
      status: 200,
      statusText: "OK",
      headers: {},
      config,
    });
  };
});

afterEach(() => {
  api.defaults.adapter = originalAdapter;
});

describe("plan uploads", () => {
  it("declares multipart so the native layer can attach its own boundary", async () => {
    await matchPhoto(photo);
    expect(contentType(seen)).toBe("multipart/form-data");
  });

  it("never lets the instance-wide json content type reach a file upload", async () => {
    await matchPhoto(photo);
    expect(contentType(seen)).not.toBe("application/json");
  });

  it("sends the picked file under the image part the backend reads", async () => {
    await matchPhoto(photo);
    expect(seen!.data).toBeInstanceOf(FormData);
    expect((seen!.data as FormData).has("image")).toBe(true);
  });

  it("outlives the 15s instance default while subtitles and the LLM run", async () => {
    await importContent({ url: "https://youtu.be/x" });
    expect(seen!.timeout).toBe(180_000);
  });

  it("keeps a json body on the url import path", async () => {
    await importContent({ url: "https://youtu.be/x" });
    expect(contentType(seen)).toBe("application/json");
  });
});
