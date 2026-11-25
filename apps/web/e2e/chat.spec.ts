import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { ANSWERED, mockApi, sse } from "./mock-api";

const conversation = (page: import("@playwright/test").Page) =>
  page.getByRole("list", { name: "Conversation" });

async function ask(page: import("@playwright/test").Page, question: string) {
  await page.getByLabel("Your question").fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
}

test("streams a cited answer with linked chips, evidence and transparency", async ({ page }) => {
  const { chatRequests } = await mockApi(page);
  await page.goto("/");
  await page.locator("label", { hasText: "Engineer" }).click();
  await ask(page, "How does the widget sorter work?");

  const answer = page.getByRole("list", { name: "Conversation" });
  await expect(answer.getByText("It sorts fictional widgets by colour")).toBeVisible();
  const chip = page.getByRole("link", { name: "Source 1: Example Widget Sorter, Overview" });
  await expect(chip).toHaveAttribute("href", "/projects/example-widget-sorter#overview");
  await expect(
    page.getByRole("link", { name: "Source 2: Example Widget Sorter, Results" }),
  ).toBeVisible();
  await expect(answer.getByText("[c1]")).toHaveCount(0);

  // Focus on a chip highlights its evidence card.
  await chip.focus();
  const card = page.locator('[id$="-c1"]').first();
  await expect(card).toHaveClass(/border-accent/);
  await expect(
    page.getByText("A fictional excerpt from the fixture corpus.").first(),
  ).toBeVisible();

  await page.getByRole("button", { name: "How this answer was made" }).click();
  const drawer = page.getByRole("dialog", { name: "How this answer was made" });
  await expect(drawer.getByText("Index version")).toBeVisible();
  await expect(drawer.getByText("Removed citation(s) the model invented: c9.")).toBeVisible();
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(axe.violations).toEqual([]);

  // The recruiter role never leaves the browser.
  expect(chatRequests).toHaveLength(1);
  expect(Object.keys(chatRequests[0]).sort()).toEqual(["history", "question"]);
  expect(JSON.stringify(chatRequests[0])).not.toContain("engineer");
});

test("screen readers hear sentences, not tokens", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  const live = page.locator('[aria-live="polite"]');
  await ask(page, "How does the widget sorter work?");
  await expect(live).toContainText("Answer complete.");
  await expect(live).not.toContainText("[c");
});

test("follow-up questions send history", async ({ page }) => {
  const { chatRequests } = await mockApi(page);
  await page.goto("/");
  await ask(page, "How does the widget sorter work?");
  await expect(page.getByRole("button", { name: "How this answer was made" })).toBeVisible();
  await ask(page, "Why?");
  await expect(page.getByRole("button", { name: "How this answer was made" })).toHaveCount(2);
  expect(chatRequests[1].history).toEqual([
    {
      question: "How does the widget sorter work?",
      answer: "It sorts fictional widgets by colour. Its results section is fictional too.",
    },
  ]);
});

test("no-evidence answers offer related topics", async ({ page }) => {
  await mockApi(page, {
    chat: sse([
      ["retrieval", { method: "hybrid", index_version: 7, timings_ms: {}, chunks: [] }],
      [
        "token",
        { text: "I couldn't find anything in Michael's published write-ups that answers that." },
      ],
      ["citations", { used: [], removed: [], unsupported: [] }],
      ["done", { status: "no_evidence", suggestions: ["Example Chess Engine"] }],
    ]),
  });
  await page.goto("/");
  await ask(page, "What is the best pizza topping?");
  await expect(conversation(page).getByText("couldn't find anything")).toBeVisible();
  await expect(page.getByRole("button", { name: "Ask about Example Chess Engine" })).toBeVisible();
});

test("rate limits and the spend cap show friendly errors", async ({ page }) => {
  let calls = 0;
  await mockApi(page, {
    chat: () => {
      calls += 1;
      return calls === 1
        ? {
            status: 429,
            body: sse([["error", { code: "rate_limited", message: "Slow down, please." }]]),
          }
        : {
            status: 503,
            body: sse([["error", { code: "spend_cap", message: "The guide is resting." }]]),
          };
    },
  });
  await page.goto("/");
  await ask(page, "First question");
  await expect(conversation(page).getByRole("alert")).toContainText("Slow down, please.");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  await ask(page, "Second question");
  await expect(conversation(page).getByRole("alert").last()).toContainText("The guide is resting.");
  await expect(page.getByRole("button", { name: "Try again" })).toHaveCount(1);
});

test("a broken stream becomes an error, not a hang", async ({ page }) => {
  await mockApi(page, { chat: sse([["token", { text: "Half an ans" }]]) });
  await page.goto("/");
  await ask(page, "Question");
  await expect(conversation(page).getByRole("alert")).toContainText("couldn't answer just now");
});

test("expired sessions are renewed once automatically", async ({ page }) => {
  let calls = 0;
  await mockApi(page, {
    chat: () => {
      calls += 1;
      return calls === 1
        ? { status: 401, body: sse([["error", { code: "invalid_session", message: "Expired." }]]) }
        : { status: 200, body: ANSWERED };
    },
  });
  await page.goto("/");
  await ask(page, "Question");
  await expect(page.getByText("It sorts fictional widgets by colour")).toBeVisible();
  expect(calls).toBe(2);
});

test("offline visitors are told before anything is sent", async ({ page, context }) => {
  const { chatRequests } = await mockApi(page);
  await page.goto("/");
  await context.setOffline(true);
  await expect(page.getByText("You seem to be offline.").first()).toBeVisible();
  await ask(page, "Question");
  await expect(conversation(page).getByRole("alert")).toContainText("offline");
  expect(chatRequests).toHaveLength(0);
  await context.setOffline(false);
});

test("a slow API shows the waking message", async ({ page }) => {
  await mockApi(page, { healthDelayMs: 3000 });
  await page.goto("/");
  await expect(page.getByText("Waking the guide.")).toBeVisible();
  await expect(page.getByText("Waking the guide.")).toHaveCount(0, { timeout: 5000 });
});

test("reviewed starter answers are served without calling the API", async ({ page }) => {
  const { chatRequests } = await mockApi(page);
  await page.goto("/");
  await page.getByRole("button", { name: "What kinds of projects has Michael worked on?" }).click();
  await expect(page.getByText("Pre-written answer, reviewed by Michael")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Source 2: Example Chess Engine, Overview" }),
  ).toHaveAttribute("href", "/projects/example-chess-engine#overview");
  expect(chatRequests).toHaveLength(0);
});

test("unreviewed starter answers are never shown", async ({ page }) => {
  const { chatRequests } = await mockApi(page);
  await page.goto("/");
  await page.locator("label", { hasText: "Recruiter" }).click();
  await page
    .getByRole("button", { name: "Which languages and tools appear across his projects?" })
    .click();
  await expect(page.getByText("It sorts fictional widgets by colour")).toBeVisible();
  await expect(page.getByText("This draft answer must never be shown")).toHaveCount(0);
  expect(chatRequests).toHaveLength(1);
});

test("recruiter mode changes starter questions and project order only", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  const starters = page
    .getByRole("list")
    .filter({ has: page.getByRole("button", { name: /\?$/ }) });
  const before = await starters.first().innerText();
  await page.locator("label", { hasText: "Hiring manager" }).click();
  await expect(starters.first()).not.toHaveText(before);
  await page.goto("/projects");
  await expect(page.getByRole("row")).toHaveCount(4);
});

test("Ask about this project scopes the question", async ({ page }) => {
  const { chatRequests } = await mockApi(page);
  await page.goto("/projects/example-widget-sorter");
  await page.getByRole("link", { name: "Ask about this project" }).click();
  await expect(page).toHaveURL(/\/ask\?project=example-widget-sorter$/);
  await expect(page.getByText("Asking about")).toContainText("Example Widget Sorter");
  await ask(page, "What was hard?");
  await expect(page.getByText("It sorts fictional widgets by colour")).toBeVisible();
  expect(chatRequests[0].project).toBe("example-widget-sorter");
});

test("the conversation survives a reload in the same tab", async ({ page }) => {
  await mockApi(page);
  await page.goto("/ask");
  await ask(page, "How does the widget sorter work?");
  await expect(page.getByText("It sorts fictional widgets by colour")).toBeVisible();
  await page.reload();
  await expect(page.getByText("It sorts fictional widgets by colour")).toBeVisible();
});
