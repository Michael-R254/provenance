import { describe, expect, it } from "vitest";

import { SseParser } from "./sse";

describe("SseParser", () => {
  it("parses events split across arbitrary chunks", () => {
    const parser = new SseParser();
    const stream =
      'event: token\ndata: {"text":"Hel"}\n\nevent: token\ndata: {"text":"lo"}\n\nevent: done\ndata: {"status":"answered"}\n\n';
    const events = [...stream].flatMap((ch) => parser.feed(ch));
    expect(events).toEqual([
      { event: "token", data: { text: "Hel" } },
      { event: "token", data: { text: "lo" } },
      { event: "done", data: { status: "answered" } },
    ]);
  });

  it("ignores comments, unknown events and broken JSON", () => {
    const parser = new SseParser();
    const events = parser.feed(
      ': keep-alive\n\nevent: other\ndata: {}\n\nevent: token\ndata: {broken\n\nevent: error\r\ndata: {"code":"rate_limited","message":"m"}\r\n\r\n',
    );
    expect(events).toEqual([{ event: "error", data: { code: "rate_limited", message: "m" } }]);
  });
});
