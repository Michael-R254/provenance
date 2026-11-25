import type { ChatEvent, ChatRequest, ErrorEvent } from "./chat-types";
import { SseParser } from "./sse";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

const SESSION_KEY = "provenance-session";

type StoredSession = { token: string; expiresAt: number };

export const MESSAGES: Record<ErrorEvent["code"], string> = {
  invalid_session: "Your session has expired. Refresh the page to keep asking.",
  rate_limited: "You're asking faster than the guide can keep up. Wait a minute and retry.",
  spend_cap: "The guide is resting for today. Please come back tomorrow.",
  input_too_long: "That question is too long. Please shorten it and try again.",
  unavailable: "The guide couldn't answer just now. Please try again shortly.",
  offline: "You seem to be offline. Check your connection and try again.",
};

/** Pings /health so a scaled-to-zero API starts waking while the visitor reads the page. */
export async function warmUp(signal?: AbortSignal): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/health`, { signal, cache: "no-store" });
    return response.ok;
  } catch {
    return false;
  }
}

function readSession(): StoredSession | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    const parsed = raw ? (JSON.parse(raw) as StoredSession) : null;
    return parsed && parsed.expiresAt * 1000 > Date.now() + 30_000 ? parsed : null;
  } catch {
    return null;
  }
}

export function forgetSession() {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // Storage unavailable: nothing stored.
  }
}

export type TurnstileProvider = () => Promise<string>;

export async function getSession(turnstile: TurnstileProvider): Promise<string | ErrorEvent> {
  const cached = readSession();
  if (cached) return cached.token;
  let response: Response;
  try {
    response = await fetch(`${API_URL}/v1/session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ turnstile_token: await turnstile() }),
    });
  } catch {
    return { code: "offline", message: MESSAGES.offline };
  }
  if (response.status === 429) return { code: "rate_limited", message: MESSAGES.rate_limited };
  if (!response.ok) return { code: "unavailable", message: MESSAGES.unavailable };
  const body = (await response.json()) as { session_token: string; expires_at: number };
  try {
    sessionStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ token: body.session_token, expiresAt: body.expires_at }),
    );
  } catch {
    // Storage unavailable: the token lives for this page only.
  }
  return body.session_token;
}

/** Streams one answer. Yields parsed events; network failures become an `error` event. */
export async function* streamChat(
  request: ChatRequest,
  token: string,
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/v1/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(request),
      signal,
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") return;
    yield { event: "error", data: { code: "offline", message: MESSAGES.offline } };
    return;
  }
  if (!response.body) {
    yield { event: "error", data: { code: "unavailable", message: MESSAGES.unavailable } };
    return;
  }
  const parser = new SseParser();
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let sawEnd = false;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      for (const event of parser.feed(value)) {
        if (event.event === "done" || event.event === "error") sawEnd = true;
        yield event;
      }
    }
  } catch (error) {
    if ((error as Error).name === "AbortError") return;
  }
  if (!sawEnd) {
    yield { event: "error", data: { code: "unavailable", message: MESSAGES.unavailable } };
  }
}

export type Source = {
  chunk_id: number;
  title: string;
  section: string;
  url: string;
  text: string;
};

export async function fetchSource(chunkId: number): Promise<Source | null> {
  try {
    const response = await fetch(`${API_URL}/v1/sources/${chunkId}`);
    return response.ok ? ((await response.json()) as Source) : null;
  } catch {
    return null;
  }
}
