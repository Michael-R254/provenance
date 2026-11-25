import type { ChatEvent } from "./chat-types";

const KNOWN = new Set(["retrieval", "token", "citations", "done", "error"]);

/** Incremental parser for `text/event-stream`. Feed it decoded chunks as they arrive. */
export class SseParser {
  private buffer = "";

  feed(chunk: string): ChatEvent[] {
    this.buffer += chunk.replaceAll("\r\n", "\n");
    const events: ChatEvent[] = [];
    let end: number;
    while ((end = this.buffer.indexOf("\n\n")) !== -1) {
      const block = this.buffer.slice(0, end);
      this.buffer = this.buffer.slice(end + 2);
      const parsed = parseBlock(block);
      if (parsed) events.push(parsed);
    }
    return events;
  }
}

function parseBlock(block: string): ChatEvent | null {
  let name = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") name = value;
    else if (field === "data") data.push(value);
  }
  if (!KNOWN.has(name) || data.length === 0) return null;
  try {
    return { event: name, data: JSON.parse(data.join("\n")) } as ChatEvent;
  } catch {
    return null;
  }
}
