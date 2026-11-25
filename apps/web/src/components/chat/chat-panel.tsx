"use client";

import { useMemo, useState } from "react";

import { AnswerText, numberCitations } from "./answer";
import { EvidenceList, EvidenceSheet } from "./evidence";
import { RolePicker } from "./role-picker";
import { TransparencyDrawer } from "./transparency";
import { citationMap, type Turn, useChat } from "./use-chat";
import { useRole } from "./use-role";
import type { Citation } from "@/lib/chat-types";
import type { StarterAnswer } from "@/lib/content";
import { STARTERS } from "@/lib/recruiter";

type Props = {
  starterAnswers: Record<string, StarterAnswer>;
  project?: { slug: string; title: string };
  onClearProject?: () => void;
  maxQuestionChars?: number;
};

export function ChatPanel({
  starterAnswers,
  project,
  onClearProject,
  maxQuestionChars = 500,
}: Props) {
  const chat = useChat(starterAnswers);
  const [role] = useRole();
  const [question, setQuestion] = useState("");
  const [highlight, setHighlight] = useState<{ turn: string; id: string } | null>(null);
  const latest = chat.turns.find((t) => t.id === highlight?.turn) ?? chat.turns.at(-1);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    void chat.ask(question, { project: project?.slug });
    setQuestion("");
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <section aria-labelledby="chat-title" className="min-w-0">
        <h2 id="chat-title" className="font-serif text-2xl font-medium">
          Ask the guide
        </h2>
        <noscript>
          <p className="mt-2 text-muted">
            The guide needs JavaScript. The project pages hold the same evidence.
          </p>
        </noscript>

        <div className="js-only mt-4 space-y-4">
          <RolePicker />
          {chat.waking && (
            <p role="status" className="font-mono text-sm text-muted">
              Waking the guide. The first answer can take a few seconds.
            </p>
          )}
          {!chat.online && (
            <p role="status" className="font-mono text-sm text-warn">
              You seem to be offline. Questions will work again when you reconnect.
            </p>
          )}
          {chat.turns.length === 0 && (
            <div>
              <h3 className="font-mono text-sm text-muted">Try asking</h3>
              <ul className="mt-2 flex flex-col items-start gap-2">
                {STARTERS[role].map((s) => (
                  <li key={s.id}>
                    <button
                      type="button"
                      onClick={() => void chat.ask(s.question, { starterId: s.id })}
                      className="rounded border border-line bg-surface px-3 py-2 text-left hover:border-accent"
                    >
                      {s.question}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <ol className="space-y-10" aria-label="Conversation">
            {chat.turns.map((turn) => (
              <TurnView
                key={turn.id}
                turn={turn}
                highlighted={highlight?.turn === turn.id ? highlight.id : null}
                onHighlight={(id) => setHighlight(id ? { turn: turn.id, id } : null)}
                onAsk={(q) => void chat.ask(q)}
                onRetry={() => void chat.ask(turn.question, { project: turn.project })}
              />
            ))}
          </ol>

          <form onSubmit={submit} className="space-y-2">
            {project && (
              <p className="flex items-center gap-2 font-mono text-sm">
                Asking about <strong className="font-sans">{project.title}</strong>
                {onClearProject && (
                  <button type="button" onClick={onClearProject} className="underline">
                    Ask about everything
                  </button>
                )}
              </p>
            )}
            <label htmlFor="question" className="block font-mono text-sm">
              Your question
            </label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <textarea
                id="question"
                rows={2}
                maxLength={maxQuestionChars}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    e.currentTarget.form?.requestSubmit();
                  }
                }}
                className="min-h-12 flex-1 resize-y rounded border border-line bg-surface px-3 py-2"
              />
              {chat.busy ? (
                <button
                  type="button"
                  onClick={chat.stop}
                  className="rounded border border-line px-4 py-2"
                >
                  Stop
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!question.trim()}
                  className="rounded bg-accent px-4 py-2 text-accent-ink disabled:opacity-50"
                >
                  Ask
                </button>
              )}
            </div>
            {chat.turns.length > 0 && !chat.busy && (
              <button type="button" onClick={chat.clear} className="font-mono text-sm underline">
                Start a new conversation
              </button>
            )}
          </form>
        </div>
        <div aria-live="polite" aria-atomic="true" className="sr-only">
          {chat.announcement}
        </div>
      </section>

      <aside aria-labelledby="evidence-title" className="js-only hidden lg:block">
        <h2 id="evidence-title" className="font-serif text-2xl font-medium">
          Evidence
        </h2>
        <div className="mt-4 lg:sticky lg:top-6">
          {latest ? (
            <EvidenceList
              turnId={latest.id}
              citations={evidenceFor(latest)}
              numbers={numberCitations(latest.text)}
              highlighted={highlight?.turn === latest.id ? highlight.id : null}
            />
          ) : (
            <p className="text-sm text-muted">Sources for each answer appear here.</p>
          )}
        </div>
      </aside>
    </div>
  );
}

function evidenceFor(turn: Turn): Citation[] {
  if (turn.citations) return turn.citations.used;
  return turn.retrieval?.chunks ?? [];
}

type TurnProps = {
  turn: Turn;
  highlighted: string | null;
  onHighlight: (id: string | null) => void;
  onAsk: (question: string) => void;
  onRetry: () => void;
};

function TurnView({ turn, highlighted, onHighlight, onAsk, onRetry }: TurnProps) {
  const citations = useMemo(() => citationMap(turn), [turn]);
  const numbers = useMemo(() => numberCitations(turn.text), [turn.text]);
  const noEvidence = turn.done?.status === "no_evidence";

  return (
    <li className="space-y-3" aria-busy={turn.status === "streaming"}>
      <p className="font-serif text-xl">{turn.question}</p>
      {turn.prewritten && (
        <p className="font-mono text-xs text-muted">Pre-written answer, reviewed by Michael</p>
      )}
      {turn.status === "streaming" && turn.text === "" && (
        <p className="font-mono text-sm text-muted">Searching the write-ups…</p>
      )}
      {turn.text && (
        <AnswerText
          text={turn.text}
          citations={citations}
          numbers={numbers}
          onHighlight={onHighlight}
        />
      )}
      {noEvidence && turn.done?.suggestions && turn.done.suggestions.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {turn.done.suggestions.map((topic) => (
            <li key={topic}>
              <button
                type="button"
                onClick={() => onAsk(`What did Michael do in ${topic}?`)}
                className="rounded border border-line px-3 py-1.5 text-sm hover:border-accent"
              >
                Ask about {topic}
              </button>
            </li>
          ))}
        </ul>
      )}
      {turn.status === "error" && turn.error && (
        <div role="alert" className="rounded border border-warn p-3">
          <p>{turn.error.message}</p>
          {turn.error.code !== "spend_cap" && turn.error.code !== "input_too_long" && (
            <button type="button" onClick={onRetry} className="mt-2 font-mono text-sm underline">
              Try again
            </button>
          )}
        </div>
      )}
      {turn.status === "done" && !noEvidence && (
        <div className="flex flex-wrap gap-2">
          <EvidenceSheet
            turnId={turn.id}
            citations={evidenceFor(turn)}
            numbers={numbers}
            highlighted={highlighted}
          />
          <TransparencyDrawer turn={turn} />
        </div>
      )}
    </li>
  );
}
