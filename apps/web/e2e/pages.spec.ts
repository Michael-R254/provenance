import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const PAGES = [
  { path: "/", heading: /Michael Rollinson/ },
  { path: "/projects", heading: "Projects" },
  { path: "/projects/example-widget-sorter", heading: "Example Widget Sorter" },
  { path: "/about", heading: "About" },
  { path: "/no-such-page", heading: "Nothing published here" },
];

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

for (const theme of ["light", "dark"] as const) {
  test.describe(`${theme} theme`, () => {
    test.use({ colorScheme: theme });
    for (const { path, heading } of PAGES) {
      test(`${path} renders with no axe violations`, async ({ page }) => {
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
        await expectNoAxeViolations(page);
      });
    }
  });
}

test("the open command palette has no axe violations", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("ControlOrMeta+k");
  await expect(page.getByRole("dialog", { name: "Search the site" })).toBeVisible();
  await expectNoAxeViolations(page);
});

test("draft projects are never published", async ({ page }) => {
  // With Cache Components the shell streams first, so the status is 200; Next.js marks the
  // page noindex and shows the not-found UI. What matters is that no draft text is served.
  const response = await page.goto("/projects/example-recipe-planner");
  const html = (await response?.text()) ?? "";
  expect(html).not.toMatch(/recipe planner/i);
  await expect(
    page.getByRole("heading", { level: 1, name: "Nothing published here" }),
  ).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  await page.goto("/projects");
  await expect(page.getByRole("link", { name: "Example Widget Sorter" })).toBeVisible();
  await expect(page.getByText(/recipe planner/i)).toHaveCount(0);
  await page.keyboard.press("ControlOrMeta+k");
  await page.getByRole("combobox").fill("recipe");
  await expect(page.getByRole("option", { name: "No matches" })).toBeVisible();
});

test("project sections carry the same anchors as ingestion", async ({ page }) => {
  await page.goto("/projects/example-widget-sorter");
  for (const id of ["example-widget-sorter", "overview", "my-contributions", "results"]) {
    await expect(page.locator(`[id="${id}"]`)).toHaveCount(1);
  }
  await page
    .getByRole("navigation", { name: "On this page" })
    .getByRole("link", { name: "Results" })
    .click();
  await expect(page).toHaveURL(/#results$/);
});

test("pages are served with security headers", async ({ request }) => {
  const response = await request.get("/");
  const headers = response.headers();
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
  expect(headers["x-powered-by"]).toBeUndefined();
});
