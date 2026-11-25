/** Splits answer text into plain text and citation markers like [c1]. */
export type Segment = { kind: "text"; text: string } | { kind: "cite"; id: string };

export function segments(text: string): Segment[] {
  const out: Segment[] = [];
  const pattern = /\[(c\d{1,3})\]/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) out.push({ kind: "text", text: text.slice(last, match.index) });
    out.push({ kind: "cite", id: match[1] });
    last = match.index + match[0].length;
  }
  if (last < text.length) out.push({ kind: "text", text: text.slice(last) });
  return out;
}

/** Text for screen readers and history: citation markers removed, spacing tidied. */
export function plainText(text: string): string {
  return text
    .replace(/\s*\[c\d{1,3}\]/g, "")
    .replace(/\s+([.,;:!?])/g, "$1")
    .trim();
}

/**
 * Collects streamed text and releases whole sentences, so screen readers hear one polite
 * announcement per sentence rather than one per token.
 */
export class SentenceBuffer {
  private pending = "";

  push(delta: string): string[] {
    this.pending += delta;
    const sentences: string[] = [];
    const boundary = /[.!?](?:\s*\[c\d{1,3}\])*\s+(?=\S)/g;
    let start = 0;
    for (const match of this.pending.matchAll(boundary)) {
      const end = match.index + match[0].length;
      const sentence = plainText(this.pending.slice(start, end));
      if (sentence) sentences.push(sentence);
      start = end;
    }
    this.pending = this.pending.slice(start);
    return sentences;
  }

  flush(): string[] {
    const rest = plainText(this.pending);
    this.pending = "";
    return rest ? [rest] : [];
  }
}
