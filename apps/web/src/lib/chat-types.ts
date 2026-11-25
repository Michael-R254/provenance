/** Shapes of the `/v1/chat` server-sent events (docs/architecture.md section 6). */

export type RetrievedChunk = {
  id: string;
  chunk_id: number;
  title: string;
  section: string;
  url: string;
  project: string | null;
  vector_score: number | null;
  keyword_score: number | null;
  fused_score: number;
};

export type RetrievalEvent = {
  method: string;
  index_version: number;
  timings_ms: Record<string, number>;
  chunks: RetrievedChunk[];
};

export type Citation = {
  id: string;
  chunk_id?: number;
  title: string;
  section: string;
  url: string;
};

export type CitationsEvent = { used: Citation[]; removed: string[]; unsupported: string[] };
export type DoneEvent = { status: "answered" | "no_evidence" | "refused"; suggestions?: string[] };
export type ErrorEvent = { code: ErrorCode; message: string };
export type ErrorCode =
  "invalid_session" | "rate_limited" | "spend_cap" | "input_too_long" | "unavailable" | "offline";

export type ChatEvent =
  | { event: "retrieval"; data: RetrievalEvent }
  | { event: "token"; data: { text: string } }
  | { event: "citations"; data: CitationsEvent }
  | { event: "done"; data: DoneEvent }
  | { event: "error"; data: ErrorEvent };

export type HistoryTurn = { question: string; answer: string };

/** What the browser sends. There is deliberately no `role` (AGENTS.md rule 6). */
export type ChatRequest = { question: string; history: HistoryTurn[]; project?: string };
