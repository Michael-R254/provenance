import { expect, test } from "@playwright/test";

test("skip link moves focus to the main content", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#main$/);
});

test("the command palette works from the keyboard alone", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("ControlOrMeta+k");
  const input = page.getByRole("combobox", { name: /search/i });
  await expect(input).toBeFocused();
  await page.keyboard.type("widget results");
  await expect(page.getByRole("option").first()).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/projects\/example-widget-sorter#results$/);
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("Escape closes the palette and returns focus", async ({ page }) => {
  await page.goto("/projects");
  const trigger = page.getByRole("button", { name: /search/i });
  await trigger.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test("theme toggle switches theme and remembers it", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("button", { name: "Switch to light theme" })).toBeVisible();
});

test("project filter narrows the table", async ({ page }) => {
  await page.goto("/projects");
  await page.getByRole("searchbox", { name: "Filter" }).fill("chess");
  await expect(page.getByRole("row")).toHaveCount(2); // header + one project
  await expect(page.getByText("1 of 3 shown")).toBeVisible();
});

test.describe("without JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  test("pages still render their content and hide JS-only controls", async ({ page }) => {
    await page.goto("/projects/example-widget-sorter");
    await expect(
      page.getByRole("heading", { level: 1, name: "Example Widget Sorter" }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "Overview" })).toBeVisible();
    await expect(page.getByRole("button", { name: /search|theme/i })).toHaveCount(0);
    await page.goto("/projects");
    await expect(page.getByRole("link", { name: "Example Chess Engine" })).toBeVisible();
  });
});

test.describe("reduced motion", () => {
  test.use({ reducedMotion: "reduce" });

  test("disables transitions", async ({ page }) => {
    await page.goto("/");
    const duration = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--duration").trim(),
    );
    expect(duration).toMatch(/^0m?s$/);
  });
});
