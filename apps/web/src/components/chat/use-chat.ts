"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { plainText, SentenceBuffer } from "@/lib/answer-text";
import { forgetSession, getSession, MESSAGES, streamChat, warmUp } from "@/lib/api";
import type {
  Citation,
  CitationsEvent,
  DoneEvent,
  ErrorEvent,
  HistoryTurn,
  RetrievalEvent,
} from "@/lib/chat-types";
import type { StarterAnswer } from "@/lib/content";
import { turnstileToken } from "@/lib/turnstile";

export type Turn = {
  id: string;
  question: string;
  project?: string;
  status: "streaming" | "done" | "error";
  text: string;
  retrieval?: RetrievalEvent;
  citations?: CitationsEvent;
  done?: DoneEvent;
  error?: ErrorEvent;
  prewritten?: boolean;
};

type Action =
  | { type: "start"; turn: Turn }
  | { type: "patch"; id: string; patch: Partial<Turn> }
  | { type: "token"; id: string; text: string }
  | { type: "restore"; turns: Turn[] }
  | { type: "clear" };

function reducer(turns: Turn[], action: Action): Turn[] {
  switch (action.type) {
    case "start":
      return [...turns, action.turn];
    case "patch":
      return turns.map((t) => (t.id === action.id ? { ...t, ...action.patch } : t));
    case "token":
      return turns.map((t) => (t.id === action.id ? { ...t, text: t.text + action.text } : t));
    case "restore":
      return action.turns;
    case "clear":
      return [];
  }
}

const HISTORY_KEY = "provenance-conversation";
const MAX_HISTORY = 3;

/** Citations of a finished turn, or the retrieved chunks while it streams. */
export function citationMap(turn: Turn): Record<string, Citation> {
  const list: Citation[] = turn.citations?.used ?? turn.retrieval?.chunks ?? [];
  return Object.fromEntries(list.map((c) => [c.id, c]));
}

export function useChat(starterAnswers: Record<string, StarterAnswer>) {
  const [turns, dispatch] = useReducer(reducer, []);
  const [announcement, setAnnouncement] = useState("");
  const [waking, setWaking] = useState(false);
  const [online, setOnline] = useState(true);
  const abort = useRef<AbortController | null>(null);
  const restored = useRef(false);

  // Restore this tab's conversation, wake the API, and track connectivity.
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(HISTORY_KEY);
      if (saved) {
        const parsed = (JSON.parse(saved) as Turn[]).filter((t) => t.status !== "streaming");
        dispatch({ type: "restore", turns: parsed });
      }
    } catch {
      // Ignore unreadable history.
    }
    restored.current = true;

    const controller = new AbortController();
    const slow = setTimeout(() => setWaking(true), 1500);
    void warmUp(controller.signal).finally(() => {
      clearTimeout(slow);
      setWaking(false);
    });

    const update = () => setOnline(navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      controller.abort();
      clearTimeout(slow);
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  useEffect(() => {
    if (!restored.current) return;
    try {
      sessionStorage.setItem(HISTORY_KEY, JSON.stringify(turns.slice(-20)));
    } catch {
      // Storage full or unavailable: history lasts for this page only.
    }
  }, [turns]);

  const busy = turns.some((t) => t.status === "streaming");

  const ask = useCallback(
    async (question: string, options: { project?: string; starterId?: string } = {}) => {
      const trimmed = question.trim();
      if (!trimmed || busy) return;
      const id = `t${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

      const starter = options.starterId ? starterAnswers[options.starterId] : undefined;
      if (starter) {
        const used = Object.entries(starter.citations).map(([cid, c]) => ({
          id: cid,
          title: c.title,
          section: c.section,
          url: c.href,
        }));
        dispatch({
          type: "start",
          turn: {
            id,
            question: trimmed,
            status: "done",
            text: starter.answer,
            prewritten: true,
            citations: { used, removed: [], unsupported: [] },
            done: { status: "answered" },
          },
        });
        setAnnouncement(`Answer: ${plainText(starter.answer)}`);
        return;
      }

      const history: HistoryTurn[] = turns
        .filter((t) => t.status === "done" && t.done?.status === "answered")
        .slice(-MAX_HISTORY)
        .map((t) => ({ question: t.question, answer: plainText(t.text) }));
      dispatch({
        type: "start",
        turn: { id, question: trimmed, project: options.project, status: "streaming", text: "" },
      });
      setAnnouncement("Searching the write-ups…");

      if (!navigator.onLine) {
        const error: ErrorEvent = { code: "offline", message: MESSAGES.offline };
        dispatch({ type: "patch", id, patch: { status: "error", error } });
        setAnnouncement(error.message);
        return;
      }

      const controller = new AbortController();
      abort.current = controller;
      const sentences = new SentenceBuffer();
      const request = {
        question: trimmed,
        history,
        ...(options.project ? { project: options.project } : {}),
      };

      for (let attempt = 0; attempt < 2; attempt++) {
        const token = await getSession(turnstileToken);
        if (typeof token !== "string") {
          dispatch({ type: "patch", id, patch: { status: "error", error: token } });
          setAnnouncement(token.message);
          return;
        }
        let retry = false;
        for await (const event of streamChat(request, token, controller.signal)) {
          switch (event.event) {
            case "retrieval":
              dispatch({ type: "patch", id, patch: { retrieval: event.data } });
              break;
            case "token": {
              dispatch({ type: "token", id, text: event.data.text });
              const spoken = sentences.push(event.data.text);
              if (spoken.length > 0) setAnnouncement(spoken.join(" "));
              break;
            }
            case "citations":
              dispatch({ type: "patch", id, patch: { citations: event.data } });
              break;
            case "done": {
              const rest = sentences.flush();
              dispatch({ type: "patch", id, patch: { status: "done", done: event.data } });
              const sources = event.data.status === "answered" ? " Answer complete." : "";
              setAnnouncement(`${rest.join(" ")}${sources}`.trim());
              break;
            }
            case "error":
              if (event.data.code === "invalid_session" && attempt === 0) {
                forgetSession();
                retry = true;
                break;
              }
              dispatch({ type: "patch", id, patch: { status: "error", error: event.data } });
              setAnnouncement(event.data.message);
              break;
          }
        }
        if (!retry) break;
      }
      if (controller.signal.aborted) {
        dispatch({ type: "patch", id, patch: { status: "done", done: { status: "answered" } } });
        setAnnouncement("Stopped.");
      }
      abort.current = null;
    },
    [busy, starterAnswers, turns],
  );

  const stop = useCallback(() => abort.current?.abort(), []);
  const clear = useCallback(() => dispatch({ type: "clear" }), []);

  return { turns, ask, stop, clear, busy, announcement, waking, online };
}
