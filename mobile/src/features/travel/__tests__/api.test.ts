import type { InternalAxiosRequestConfig } from "axios";
import { api } from "@/lib/api-client";
import { askAgent, DEFAULT_CONDITIONS } from "@/features/travel/api";

const photo = { uri: "file:///a.jpg", name: "a.jpg", type: "image/jpeg" };

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
        data: { steps: [], answer: [], spots: [], totalCount: 0, suggestions: [] },
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
    await askAgent({ question: "계곡", photo, conditions: DEFAULT_CONDITIONS });
    expect(contentType(seen)).toBe("multipart/form-data");
    expect(contentType(seen)).not.toBe("application/json");
  });

  it("sends the picked file under the photo part the backend reads", async () => {
    await askAgent({ question: "계곡", photo, conditions: DEFAULT_CONDITIONS });
    const form = seen!.data as FormData;
    expect(form).toBeInstanceOf(FormData);
    expect(form.has("photo")).toBe(true);
    expect(form.get("question")).toBe("계곡");
  });

  it("carries the structured conditions on the multipart request too", async () => {
    await askAgent({
      question: "계곡",
      photo,
      conditions: { region: "capital", when: "weekend", who: "pets" },
      coords: { lat: 37.5, lng: 127.0 },
    });
    const form = seen!.data as FormData;
    expect(form.get("region")).toBe("capital");
    expect(form.get("when")).toBe("weekend");
    expect(form.get("who")).toBe("pets");
    expect(form.get("lat")).toBe("37.5");
  });

  it("keeps a json body when no photo is attached", async () => {
    await askAgent({ question: "계곡", conditions: DEFAULT_CONDITIONS });
    expect(contentType(seen)).toBe("application/json");
    expect(jsonBody(seen)).toEqual({
      question: "계곡",
      region: "all",
      when: "any",
      who: "any",
    });
  });

  it("omits coords entirely when location is unavailable", async () => {
    await askAgent({ question: "계곡", conditions: DEFAULT_CONDITIONS, coords: null });
    expect(jsonBody(seen)).not.toHaveProperty("lat");
  });

  it("outlives the 15s instance default while Gemini and pgvector run", async () => {
    await askAgent({ question: "계곡", conditions: DEFAULT_CONDITIONS });
    expect(seen!.timeout).toBe(60_000);
  });
});
