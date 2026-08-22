import { streamChat, type ChatHandlers } from "@/features/travel/api";
import { AppError } from "@/lib/app-error";

jest.mock("expo/fetch", () => ({ fetch: jest.fn() }));

const { fetch: fetchMock } = jest.requireMock("expo/fetch") as { fetch: jest.Mock };
const { File: fileMock } = jest.requireMock("expo-file-system") as { File: jest.Mock };

const encoder = new TextEncoder();

function bodyOf(chunks: string[]): ReadableStream<Uint8Array> {
  let at = 0;
  const reader = {
    read: async () => {
      if (at >= chunks.length) return { done: true as const, value: undefined };
      const value = encoder.encode(chunks[at]);
      at += 1;
      return { done: false as const, value };
    },
    cancel: async () => {},
  };
  return { getReader: () => reader } as unknown as ReadableStream<Uint8Array>;
}

function okResponse(chunks: string[]) {
  return { ok: true, status: 200, body: bodyOf(chunks), json: async () => ({}) };
}

beforeEach(() => {
  fetchMock.mockReset();
  fileMock.mockClear();
});

describe("streamChat 요청", () => {
  it("사진 없는 요청은 JSON 본문으로 /agent/chat에 보낸다", async () => {
    fetchMock.mockResolvedValueOnce(okResponse([]));

    await streamChat(
      {
        message: "정읍 맛집",
        coords: { lat: 37.5, lng: 127 },
        clientTime: "2026-08-11T21:30:00+09:00",
        context: null,
        history: [{ role: "user", text: "이전 질문" }],
      },
      {},
    );

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/agent/chat");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({
      message: "정읍 맛집",
      lat: 37.5,
      lng: 127,
      clientTime: "2026-08-11T21:30:00+09:00",
      history: [{ role: "user", text: "이전 질문" }],
    });
  });

  it("사진이 있으면 photo 파트를 담은 multipart로 보낸다", async () => {
    fetchMock.mockResolvedValueOnce(okResponse([]));
    const photo = { uri: "file:///a.jpg", name: "a.jpg", type: "image/jpeg" };

    await streamChat({ message: null, photo, coords: { lat: 37.5, lng: 127 }, history: [] }, {});

    const [, init] = fetchMock.mock.calls[0] as [string, { body: FormData; headers: object }];
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.body.has("photo")).toBe(true);
    expect(init.body.has("message")).toBe(false);
    expect(init.body.get("lat")).toBe("37.5");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("photo 파트는 uri 객체가 아니라 파일에서 읽는다", async () => {
    fetchMock.mockResolvedValueOnce(okResponse([]));
    const photo = { uri: "file:///a.jpg", name: "a.jpg", type: "image/jpeg" };

    await streamChat({ message: null, photo, history: [] }, {});

    expect(fileMock).toHaveBeenCalledWith("file:///a.jpg");
  });
});

describe("streamChat 이벤트", () => {
  it("이벤트별 콜백으로 분배한다", async () => {
    fetchMock.mockResolvedValueOnce(
      okResponse([
        'event: step\ndata: {"index":0,"label":"조회","status":"run"}\n\n',
        'event: delta\ndata: {"text":"정읍"}\n\n',
        'event: cards\ndata: {"spots":[],"tagBasis":null}\n\n',
        'event: sources\ndata: {"items":[{"kind":"kto","title":"관광정보"}]}\n\n',
        'event: done\ndata: {"answerText":"정읍","spots":[],"sources":[],"intent":{"categoryKeywords":[],"regionHints":[]},"totalCount":0}\n\n',
      ]),
    );
    const seen: string[] = [];
    const handlers: ChatHandlers = {
      onStep: () => seen.push("step"),
      onDelta: (text) => seen.push(`delta:${text}`),
      onCards: () => seen.push("cards"),
      onSources: (items) => seen.push(`sources:${items.length}`),
      onDone: (event) => seen.push(`done:${event.answerText}`),
    };

    await streamChat({ message: "정읍" }, handlers);

    expect(seen).toEqual(["step", "delta:정읍", "cards", "sources:1", "done:정읍"]);
  });

  it("error 이벤트는 onError로 흐른다", async () => {
    fetchMock.mockResolvedValueOnce(
      okResponse(['event: error\ndata: {"code":"AGENT_NO_RESULTS","message":"none"}\n\n']),
    );
    const onError = jest.fn();

    await streamChat({ message: "정읍" }, { onError });

    expect(onError).toHaveBeenCalledWith({ code: "AGENT_NO_RESULTS", message: "none" });
  });
});

describe("streamChat 실패", () => {
  it("스트림 전 실패는 JSend 봉투를 AppError로 바꾼다", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 429,
      body: null,
      json: async () => ({
        data: null,
        error: { code: "RATE_LIMITED", message: "too many" },
        meta: {},
      }),
    });

    await expect(streamChat({ message: "정읍" }, {})).rejects.toMatchObject({
      code: "RATE_LIMITED",
    });
  });

  it("네트워크 단절은 NETWORK_ERROR로 던진다", async () => {
    fetchMock.mockRejectedValueOnce(new Error("socket closed"));

    await expect(streamChat({ message: "정읍" }, {})).rejects.toEqual(expect.any(AppError));
    fetchMock.mockRejectedValueOnce(new Error("socket closed"));
    await expect(streamChat({ message: "정읍" }, {})).rejects.toMatchObject({
      code: "NETWORK_ERROR",
    });
  });

  it("이미 abort된 요청은 조용히 끝난다", async () => {
    const controller = new AbortController();
    controller.abort();
    fetchMock.mockRejectedValueOnce(new Error("aborted"));

    await expect(streamChat({ message: "정읍" }, {}, controller.signal)).resolves.toBeUndefined();
  });
});
