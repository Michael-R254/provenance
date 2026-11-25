"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useState } from "react";

import { fetchSource } from "@/lib/api";
import type { Citation } from "@/lib/chat-types";

type CardProps = {
  citation: Citation;
  number?: number;
  highlighted: boolean;
  domId: string;
};

function EvidenceCard({ citation, number, highlighted, domId }: CardProps) {
  const [excerpt, setExcerpt] = useState<string | null>(null);
  useEffect(() => {
    if (citation.chunk_id === undefined) return;
    let live = true;
    void fetchSource(citation.chunk_id).then((source) => {
      if (live && source) setExcerpt(source.text);
    });
    return () => {
      live = false;
    };
  }, [citation.chunk_id]);

  return (
    <li
      id={domId}
      className={`rounded border p-3 transition-colors duration-[var(--duration)] ${
        highlighted ? "border-accent bg-accent-soft" : "border-line bg-surface"
      }`}
    >
      <p className="font-mono text-xs text-muted">
        {number !== undefined ? `Source ${number}` : "Retrieved"} · {citation.section}
      </p>
      <a href={citation.url} className="mt-1 block font-serif text-lg underline">
        {citation.title}
      </a>
      {excerpt && <p className="mt-2 line-clamp-4 text-sm text-muted">{excerpt}</p>}
    </li>
  );
}

type RailProps = {
  turnId: string;
  citations: Citation[];
  numbers: Record<string, number>;
  highlighted: string | null;
};

export function EvidenceList({ turnId, citations, numbers, highlighted }: RailProps) {
  if (citations.length === 0) {
    return <p className="text-sm text-muted">No sources for this answer.</p>;
  }
  return (
    <ul className="space-y-3">
      {citations.map((c) => (
        <EvidenceCard
          key={c.id}
          citation={c}
          number={numbers[c.id]}
          highlighted={highlighted === c.id}
          domId={`evidence-${turnId}-${c.id}`}
        />
      ))}
    </ul>
  );
}

/** Mobile: the same list in a bottom sheet. */
export function EvidenceSheet(props: RailProps) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="rounded border border-line px-3 py-1.5 font-mono text-sm hover:border-accent lg:hidden"
        >
          Evidence ({props.citations.length})
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-ink/30" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed inset-x-0 bottom-0 max-h-[75vh] overflow-y-auto rounded-t border-t border-line bg-paper p-4"
        >
          <div className="flex items-center justify-between">
            <Dialog.Title className="font-serif text-xl">Evidence</Dialog.Title>
            <Dialog.Close className="rounded border border-line px-3 py-1 font-mono text-sm">
              Close
            </Dialog.Close>
          </div>
          <div className="mt-4">
            <EvidenceList {...props} />
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
