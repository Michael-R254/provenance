"use client";

import * as Dialog from "@radix-ui/react-dialog";

import type { Turn } from "./use-chat";

const fmt = (v: number | null | undefined, digits = 3) =>
  v === null || v === undefined ? "—" : v.toFixed(digits);

/** Shows how an answer was produced: method, timings, chunks, scores and citation checks. */
export function TransparencyDrawer({ turn }: { turn: Turn }) {
  const used = new Set(turn.citations?.used.map((c) => c.id));
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="rounded border border-line px-3 py-1.5 font-mono text-sm hover:border-accent"
        >
          How this answer was made
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-ink/30" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed inset-y-0 right-0 w-[min(40rem,100vw)] overflow-y-auto border-l border-line bg-paper p-6"
        >
          <div className="flex items-start justify-between gap-4">
            <Dialog.Title className="font-serif text-2xl">How this answer was made</Dialog.Title>
            <Dialog.Close className="rounded border border-line px-3 py-1 font-mono text-sm">
              Close
            </Dialog.Close>
          </div>
          {turn.prewritten ? (
            <p className="mt-4">
              This is a pre-written answer that Michael reviewed. It was served without calling a
              model, and its sources link to the sections it relies on.
            </p>
          ) : (
            <TransparencyDetails turn={turn} used={used} />
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function TransparencyDetails({ turn, used }: { turn: Turn; used: Set<string> }) {
  const r = turn.retrieval;
  const c = turn.citations;
  return (
    <div className="mt-6 space-y-8 text-sm">
      <section aria-labelledby="t-method">
        <h3 id="t-method" className="font-mono text-xs text-muted uppercase">
          Retrieval
        </h3>
        {r ? (
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 font-mono">
            <dt>Method</dt>
            <dd>{r.method} (vector + keyword, reciprocal rank fusion)</dd>
            <dt>Index version</dt>
            <dd>{r.index_version}</dd>
            {Object.entries(r.timings_ms).map(([stage, ms]) => (
              <div key={stage} className="contents">
                <dt>{stage}</dt>
                <dd>{ms.toFixed(1)} ms</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="mt-2">No retrieval details were received.</p>
        )}
      </section>
      {r && r.chunks.length > 0 && (
        <section aria-labelledby="t-chunks">
          <h3 id="t-chunks" className="font-mono text-xs text-muted uppercase">
            Passages shown to the model
          </h3>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full border-collapse text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-line">
                  <th scope="col" className="py-1 pr-3 font-normal">
                    ID
                  </th>
                  <th scope="col" className="py-1 pr-3 font-normal">
                    Section
                  </th>
                  <th scope="col" className="py-1 pr-3 font-normal">
                    Vector
                  </th>
                  <th scope="col" className="py-1 pr-3 font-normal">
                    Keyword
                  </th>
                  <th scope="col" className="py-1 pr-3 font-normal">
                    Fused
                  </th>
                  <th scope="col" className="py-1 font-normal">
                    Cited
                  </th>
                </tr>
              </thead>
              <tbody>
                {r.chunks.map((chunk) => (
                  <tr key={chunk.id} className="border-b border-line">
                    <td className="py-1 pr-3">{chunk.id}</td>
                    <td className="py-1 pr-3 font-sans">
                      {chunk.title} · {chunk.section}
                    </td>
                    <td className="py-1 pr-3">{fmt(chunk.vector_score)}</td>
                    <td className="py-1 pr-3">{fmt(chunk.keyword_score)}</td>
                    <td className="py-1 pr-3">{fmt(chunk.fused_score, 4)}</td>
                    <td className="py-1">{used.has(chunk.id) ? "yes" : "no"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <section aria-labelledby="t-checks">
        <h3 id="t-checks" className="font-mono text-xs text-muted uppercase">
          Citation checks
        </h3>
        {c ? (
          <ul className="mt-2 space-y-1">
            <li>{c.used.length} source(s) cited and verified.</li>
            <li>
              {c.removed.length === 0
                ? "No unknown citations."
                : `Removed citation(s) the model invented: ${c.removed.join(", ")}.`}
            </li>
            <li>
              {c.unsupported.length === 0
                ? "Every sentence carries a citation."
                : `Sentences without a citation: ${c.unsupported.length}.`}
            </li>
            {c.unsupported.map((s) => (
              <li key={s} className="border-l-2 border-warn pl-2 text-muted">
                {s}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2">No citation checks were run for this answer.</p>
        )}
      </section>
    </div>
  );
}
