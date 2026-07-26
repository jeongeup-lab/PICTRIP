import type { InternalAxiosRequestConfig } from "axios";
import { api } from "@/lib/api-client";
import { askAgent, type QueryIntent, type RefinePatch } from "@/features/travel/api";

const photo = { uri: "file:///a.jpg", name: "a.jpg", type: "image/jpeg" };

const intent: QueryIntent = {
  categoryKeywords: ["계곡"],
  regionHints: ["부산"],
  moodHints: ["sea"],
  crowdPreference: "quiet",
};
const patch: RefinePatch = { crowdPreference: "quiet" };

let seen: InternalAxiosRequestConfig | null = null;
const originalAdapter = api.defaults.adapter;

const contentType = (config: InternalAxiosRequestConfig | null) =>
  config?.headers["Content-Type"] ?? config?.headers["content-type"];

const jsonBody = (config: InternalAxiosRequestConfig | null): Record<string, unknown> =>
  typeof config?.data === "string"
    ? (JSON.parse(config.data) as Record<string, unknown>)
    : ((config?.data ?? {}) as Record<string, unknown>);

beforeEach(() => {
  seen = null;
  api.defaults.adapter = (config) => {
    seen = config;
    return Promise.resolve({
      data: {
        data: {
          steps: [],
          answer: [],
          spots: [],
          totalCount: 0,
          intent: { categoryKeywords: [], regionHints: [] },
          suggestions: [],
        },
        error: null,
        meta: {},
      },
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

describe("askAgent", () => {
  it("declares multipart so the native layer can attach its own boundary", async () => {
    await askAgent({ question: "계곡", photo });
    expect(contentType(seen)).toBe("multipart/form-data");
    expect(contentType(seen)).not.toBe("application/json");
  });

  it("sends the picked file under the photo part the backend reads", async () => {
    await askAgent({ question: "계곡", photo });
    const form = seen!.data as FormData;
    expect(form).toBeInstanceOf(FormData);
    expect(form.has("photo")).toBe(true);
    expect(form.get("question")).toBe("계곡");
  });

  it("refine 요청은 intent와 patch를 함께 보낸다", async () => {
    await askAgent({ intent, patch });
    expect(jsonBody(seen)).toEqual({ intent, patch });
  });

  it("echoes the served intent back whole so refine keeps every axis", async () => {
    await askAgent({ intent, patch });
    expect((jsonBody(seen) as { intent: QueryIntent }).intent).toEqual(intent);
  });

  it("사진 refine은 intent와 patch를 JSON 문자열로 폼에 담는다", async () => {
    await askAgent({ photo, intent, patch: { nearMe: true } });
    const form = seen!.data as FormData;
    expect(form.get("intent")).toBe(JSON.stringify(intent));
    expect(form.get("patch")).toBe(JSON.stringify({ nearMe: true }));
  });

  it("carries coords on the multipart request too", async () => {
    await askAgent({ question: "계곡", photo, coords: { lat: 37.5, lng: 127.0 } });
    const form = seen!.data as FormData;
    expect(form.get("lat")).toBe("37.5");
    expect(form.get("lng")).toBe("127");
  });

  it("keeps a json body when no photo is attached", async () => {
    await askAgent({ question: "계곡" });
    expect(contentType(seen)).toBe("application/json");
    expect(jsonBody(seen)).toEqual({ question: "계곡" });
  });

  it("omits intent and patch when the turn is a fresh question", async () => {
    await askAgent({ question: "계곡" });
    expect(jsonBody(seen)).not.toHaveProperty("intent");
    expect(jsonBody(seen)).not.toHaveProperty("patch");
  });

  it("omits intent and patch from the form when the photo turn is fresh", async () => {
    await askAgent({ question: "계곡", photo });
    const form = seen!.data as FormData;
    expect(form.has("intent")).toBe(false);
    expect(form.has("patch")).toBe(false);
  });

  it("omits coords entirely when location is unavailable", async () => {
    await askAgent({ question: "계곡", coords: null });
    expect(jsonBody(seen)).not.toHaveProperty("lat");
  });

  it("outlives the 15s instance default while Gemini and pgvector run", async () => {
    await askAgent({ question: "계곡" });
    expect(seen!.timeout).toBe(60_000);
  });
});
