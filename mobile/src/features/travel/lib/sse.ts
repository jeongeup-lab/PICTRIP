export interface SseEvent {
  event: string;
  data: string;
}

export type SseEmit = (event: SseEvent) => void;

export class SseParser {
  private buffer = "";
  private eventName: string | null = null;
  private dataLines: string[] = [];

  push(chunk: string, emit: SseEmit): void {
    this.buffer += chunk;
    let at = this.buffer.indexOf("\n");
    while (at >= 0) {
      const raw = this.buffer.slice(0, at);
      this.buffer = this.buffer.slice(at + 1);
      this.line(raw.endsWith("\r") ? raw.slice(0, -1) : raw, emit);
      at = this.buffer.indexOf("\n");
    }
  }

  flush(emit: SseEmit): void {
    if (this.buffer.length > 0) {
      const raw = this.buffer;
      this.buffer = "";
      this.line(raw.endsWith("\r") ? raw.slice(0, -1) : raw, emit);
    }
    this.dispatch(emit);
  }

  private line(line: string, emit: SseEmit): void {
    if (line === "") {
      this.dispatch(emit);
      return;
    }
    if (line.startsWith(":")) return;
    const colon = line.indexOf(":");
    const field = colon < 0 ? line : line.slice(0, colon);
    let value = colon < 0 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") this.eventName = value;
    else if (field === "data") this.dataLines.push(value);
  }

  private dispatch(emit: SseEmit): void {
    if (this.eventName === null && this.dataLines.length === 0) return;
    emit({ event: this.eventName ?? "message", data: this.dataLines.join("\n") });
    this.eventName = null;
    this.dataLines = [];
  }
}

export async function readSseStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: SseEmit,
  signal?: AbortSignal | null,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  const parser = new SseParser();
  const cancel = () => {
    void reader.cancel().catch(() => undefined);
  };
  if (signal?.aborted) {
    cancel();
    return;
  }
  signal?.addEventListener("abort", cancel);
  try {
    for (;;) {
      let result: ReadableStreamReadResult<Uint8Array>;
      try {
        result = await reader.read();
      } catch (error) {
        if (signal?.aborted) return;
        throw error;
      }
      if (signal?.aborted) return;
      if (result.done) break;
      if (result.value) parser.push(decoder.decode(result.value, { stream: true }), onEvent);
    }
    const tail = decoder.decode();
    if (tail) parser.push(tail, onEvent);
    parser.flush(onEvent);
  } finally {
    signal?.removeEventListener("abort", cancel);
  }
}
