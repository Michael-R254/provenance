import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  ContentError,
  loadProfile,
  loadProject,
  loadProjects,
  loadStarterAnswers,
} from "./content";
import { renderMarkdown } from "./markdown";

const renderSections = (body: string, title: string) => renderMarkdown(body, title).sections;

const FIXTURES = path.resolve(__dirname, "../../../../evals/fixtures/content");

function tempContent(files: Record<string, string>): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "content-"));
  for (const [name, text] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(dir, name)), { recursive: true });
    fs.writeFileSync(path.join(dir, name), text);
  }
  return dir;
}

const project = (fields: string) =>
  `---\nid: example-a\ntitle: Example A\nversion: 1\nupdated: 2026-01-01\ntype: personal\npermission: fixture\nsummary: Fictional.\n${fields}\n---\n\n## Overview\n\nText.\n`;

describe("content loader", () => {
  it("returns approved projects only, newest first", () => {
    const slugs = loadProjects(FIXTURES).map((p) => p.slug);
    expect(slugs).toContain("example-widget-sorter");
    expect(slugs).not.toContain("example-recipe-planner");
    expect(loadProject("example-recipe-planner", FIXTURES)).toBeUndefined();
  });

  it("never returns a draft, whatever else it contains", () => {
    const dir = tempContent({
      "projects/example-a.md": project("status: draft"),
      "profile.md":
        "---\nid: profile\ntitle: P\nstatus: draft\nversion: 1\nupdated: 2026-01-01\n---\n",
    });
    expect(loadProjects(dir)).toEqual([]);
    expect(loadProfile(dir)).toBeUndefined();
  });

  it("treats a missing status as not approved", () => {
    expect(loadProjects(tempContent({ "projects/example-a.md": project("") }))).toEqual([]);
  });

  it("rejects malformed approved content instead of guessing", () => {
    const bad = tempContent({ "projects/example-a.md": project("status: approved\ntype: blog") });
    expect(() => loadProjects(bad)).toThrow(ContentError);
    const misnamed = tempContent({ "projects/other.md": project("status: approved") });
    expect(() => loadProjects(misnamed)).toThrow(/file name must match/);
  });

  it("reads dates and tags", () => {
    const [p] = loadProjects(
      tempContent({ "projects/example-a.md": project("status: approved\nlanguages: [Python]") }),
    );
    expect(p.updated).toBe("2026-01-01");
    expect(p.tags.languages).toEqual(["Python"]);
    expect(p.tags.skills).toEqual([]);
  });

  it("handles an empty content folder", () => {
    expect(loadProjects(tempContent({}))).toEqual([]);
    expect(loadProfile(tempContent({}))).toBeUndefined();
  });
});

describe("starter answers", () => {
  const sections = (p: { body: string; title: string }) =>
    // Import lazily to keep this file's other tests independent of the renderer.
    renderSections(p.body, p.title);

  it("returns approved answers with resolved citations and skips drafts", () => {
    const answers = loadStarterAnswers(FIXTURES, sections);
    expect(Object.keys(answers)).toEqual(["overview"]);
    expect(answers.overview.citations.c1).toEqual({
      href: "/projects/example-widget-sorter#overview",
      title: "Example Widget Sorter",
      section: "Overview",
    });
  });

  it("fails the build when an approved answer cites a missing section", () => {
    const dir = tempContent({
      "projects/example-a.md": project("status: approved"),
      "starters.yaml":
        "answers:\n  - id: x\n    status: approved\n    answer: Claim [c1].\n    citations:\n      c1: example-a#nope\n",
    });
    expect(() => loadStarterAnswers(dir, sections)).toThrow(/not a published section/);
  });
});
