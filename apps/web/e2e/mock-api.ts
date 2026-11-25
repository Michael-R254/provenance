import type { Page, Request } from "@playwright/test";

export const API = "http://localhost:8000";

export function sse(events: [string, unknown][]): string {
  return events.map(([name, data]) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`).join("");
}

export const RETRIEVAL = {
  method: "hybrid",
  index_version: 7,
  timings_ms: { embed: 4.2, vector: 3.1, keyword: 1.4, fuse: 0.1, total: 9.3 },
  chunks: [
    {
      id: "c1",
      chunk_id: 11,
      title: "Example Widget Sorter",
      section: "Overview",
      url: "/projects/example-widget-sorter#overview",
      project: "example-widget-sorter",
      vector_score: 0.71,
      keyword_score: 0.2,
      fused_score: 0.0325,
    },
    {
      id: "c2",
      chunk_id: 12,
      title: "Example Widget Sorter",
      section: "Results",
      url: "/projects/example-widget-sorter#results",
      project: "example-widget-sorter",
      vector_score: 0.55,
      keyword_score: null,
      fused_score: 0.0161,
    },
  ],
};

export const ANSWERED = sse([
  ["retrieval", RETRIEVAL],
  ["token", { text: "It sorts fictional widgets by colour [c1]. " }],
  ["token", { text: "Its results section is fictional too [c2]." }],
  [
    "citations",
    {
      used: [
        {
          id: "c1",
          chunk_id: 11,
          title: "Example Widget Sorter",
          section: "Overview",
          url: "/projects/example-widget-sorter#overview",
        },
        {
          id: "c2",
          chunk_id: 12,
          title: "Example Widget Sorter",
          section: "Results",
          url: "/projects/example-widget-sorter#results",
        },
      ],
      removed: ["c9"],
      unsupported: [],
    },
  ],
  ["done", { status: "answered" }],
]);

type Options = {
  chat?: string | ((request: Request) => { status: number; body: string });
  sessionStatus?: number;
  healthDelayMs?: number;
};

export async function mockApi(page: Page, options: Options = {}) {
  const chatRequests: Record<string, unknown>[] = [];
  await page.route(`${API}/health`, async (route) => {
    if (options.healthDelayMs) await new Promise((r) => setTimeout(r, options.healthDelayMs));
    await route.fulfill({ json: { status: "ok", version: "test" } });
  });
  await page.route(`${API}/v1/session`, (route) =>
    route.fulfill({
      status: options.sessionStatus ?? 200,
      json:
        options.sessionStatus && options.sessionStatus !== 200
          ? { error: "rate_limited" }
          : { session_token: "test-token", expires_at: Math.floor(Date.now() / 1000) + 3600 },
    }),
  );
  await page.route(`${API}/v1/sources/*`, (route) =>
    route.fulfill({
      json: {
        chunk_id: 11,
        title: "Example Widget Sorter",
        section: "Overview",
        url: "/projects/example-widget-sorter#overview",
        text: "A fictional excerpt from the fixture corpus.",
      },
    }),
  );
  await page.route(`${API}/v1/chat`, async (route) => {
    chatRequests.push(route.request().postDataJSON() as Record<string, unknown>);
    const result =
      typeof options.chat === "function"
        ? options.chat(route.request())
        : { status: 200, body: options.chat ?? ANSWERED };
    await route.fulfill({
      status: result.status,
      headers: { "Content-Type": "text/event-stream" },
      body: result.body,
    });
  });
  return { chatRequests };
}
