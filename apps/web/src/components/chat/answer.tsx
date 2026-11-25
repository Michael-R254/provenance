"use client";

import { segments } from "@/lib/answer-text";
import type { Citation } from "@/lib/chat-types";

type Props = {
  text: string;
  citations: Record<string, Citation>;
  numbers: Record<string, number>;
  onHighlight: (id: string | null) => void;
};

/** Answer text with citation markers rendered as links to the cited section. */
export function AnswerText({ text, citations, numbers, onHighlight }: Props) {
  return (
    <p className="max-w-[65ch] leading-relaxed whitespace-pre-wrap">
      {segments(text).map((segment, i) => {
        if (segment.kind === "text") return <span key={i}>{segment.text}</span>;
        const citation = citations[segment.id];
        const n = numbers[segment.id];
        if (!citation || n === undefined) return null;
        return (
          <a
            key={i}
            href={citation.url}
            aria-label={`Source ${n}: ${citation.title}, ${citation.section}`}
            onMouseEnter={() => onHighlight(segment.id)}
            onMouseLeave={() => onHighlight(null)}
            onFocus={() => onHighlight(segment.id)}
            onBlur={() => onHighlight(null)}
            className="mx-0.5 inline-block rounded border border-accent px-1 align-baseline font-mono text-xs leading-5 text-accent no-underline hover:bg-accent hover:text-accent-ink focus-visible:bg-accent focus-visible:text-accent-ink"
          >
            {n}
          </a>
        );
      })}
    </p>
  );
}

/** Numbers citations 1, 2, 3 in order of first use. */
export function numberCitations(text: string): Record<string, number> {
  const numbers: Record<string, number> = {};
  let next = 1;
  for (const segment of segments(text)) {
    if (segment.kind === "cite" && numbers[segment.id] === undefined) numbers[segment.id] = next++;
  }
  return numbers;
}
