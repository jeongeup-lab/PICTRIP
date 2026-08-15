import { SseParser, readSseStream, type SseEvent } from "@/features/travel/lib/sse";

function collect(): { events: SseEvent[]; emit: (event: SseEvent) => void } {
  const events: SseEvent[] = [];
  return { events, emit: (event) => events.push(event) };
}

function streamOf(chunks: Uint8Array[]): ReadableStream<Uint8Array> {
  let at = 0;
  let cancelled = false;
  const reader = {
    read: async () => {
      if (cancelled || at >= chunks.length) return { done: true as const, value: undefined };
      const value = chunks[at];
      at += 1;
      return { done: false as const, value };
    },
    cancel: async () => {
      cancelled = true;
    },
    releaseLock: () => {},
  };
  return { getReader: () => reader } as unknown as ReadableStream<Uint8Array>;
}

const encoder = new TextEncoder();

describe("SseParser", () => {
  it("event와 data 라인을 하나의 이벤트로 묶는다", () => {
    const { events, emit } = collect();
    const parser = new SseParser();

    parser.push('event: delta\ndata: {"text":"안녕"}\n\n', emit);

    expect(events).toEqual([{ event: "delta", data: '{"text":"안녕"}' }]);
  });

  it("청크 경계가 라인 중간이어도 이벤트를 온전히 조립한다", () => {
    const { events, emit } = collect();
    const parser = new SseParser();

    parser.push("event: del", emit);
    parser.push('ta\ndata: {"te', emit);
    parser.push('xt":"a"}\n\n', emit);

    expect(events).toEqual([{ event: "delta", data: '{"text":"a"}' }]);
  });

  it("빈 줄마다 이벤트를 끊어 여러 이벤트를 분리한다", () => {
    const { events, emit } = collect();
    const parser = new SseParser();

    parser.push("event: step\ndata: {}\n\nevent: delta\ndata: {}\n\n", emit);

    expect(events.map((e) => e.event)).toEqual(["step", "delta"]);
  });

  it("data 여러 줄은 개행으로 잇고 event 없으면 message로 둔다", () => {
    const { events, emit } = collect();
    const parser = new SseParser();

    parser.push("data: a\ndata: b\n\n", emit);

    expect(events).toEqual([{ event: "message", data: "a\nb" }]);
  });

  it("주석 라인과 CRLF를 견딘다", () => {
    const { events, emit } = collect();
    const parser = new SseParser();

    parser.push(": keep-alive\r\nevent: done\r\ndata: {}\r\n\r\n", emit);

    expect(events).toEqual([{ event: "done", data: "{}" }]);
  });

  it("종료 빈 줄 없이 끝난 이벤트는 flush가 흘려보낸다", () => {
    const { events, emit } = collect();
    const parser = new SseParser();

    parser.push("event: done\ndata: {}", emit);
    expect(events).toHaveLength(0);

    parser.flush(emit);
    expect(events).toEqual([{ event: "done", data: "{}" }]);
  });
});

describe("readSseStream", () => {
  it("UTF-8 멀티바이트가 청크 경계에 걸려도 깨지지 않는다", async () => {
    const bytes = encoder.encode('event: delta\ndata: {"text":"정읍 맛집"}\n\n');
    const cut = 22;
    const { events, emit } = collect();

    await readSseStream(streamOf([bytes.slice(0, cut), bytes.slice(cut)]), emit);

    expect(events).toEqual([{ event: "delta", data: '{"text":"정읍 맛집"}' }]);
  });

  it("이벤트 여러 개가 한 청크에 와도 순서대로 콜백한다", async () => {
    const bytes = encoder.encode("event: step\ndata: 1\n\nevent: step\ndata: 2\n\n");
    const { events, emit } = collect();

    await readSseStream(streamOf([bytes]), emit);

    expect(events.map((e) => e.data)).toEqual(["1", "2"]);
  });

  it("이미 abort된 신호면 아무 이벤트도 흘리지 않는다", async () => {
    const controller = new AbortController();
    controller.abort();
    const { events, emit } = collect();

    await readSseStream(
      streamOf([encoder.encode("event: delta\ndata: x\n\n")]),
      emit,
      controller.signal,
    );

    expect(events).toHaveLength(0);
  });

  it("스트림 도중 abort하면 이후 이벤트를 끊는다", async () => {
    const controller = new AbortController();
    const { events } = collect();

    await readSseStream(
      streamOf([
        encoder.encode("event: delta\ndata: 1\n\n"),
        encoder.encode("event: delta\ndata: 2\n\n"),
      ]),
      (event) => {
        events.push(event);
        controller.abort();
      },
      controller.signal,
    );

    expect(events).toHaveLength(1);
  });
});
