import { describe, expect, it } from "vitest";

import { renderMarkdown } from "./markdown";

describe("renderMarkdown", () => {
  it("gives ## headings ingestion-compatible anchors, including repeats and the title", () => {
    const { html, sections, introAnchor } = renderMarkdown(
      "Intro.\n\n## Results\n\nA\n\n## Results\n\nB\n\n## Example Title\n",
      "Example Title",
    );
    expect(introAnchor).toBe("example-title");
    expect(sections.map((s) => s.anchor)).toEqual(["results", "results-1", "example-title-1"]);
    expect(html).toContain(
      '<h2 id="results"><a href="#results" class="heading-link">Results</a></h2>',
    );
  });

  it("drops raw HTML, comments, scripts and level-1 headings", () => {
    const { html } = renderMarkdown(
      "# Title\n\n<!-- private note -->\n\n<script>alert(1)</script>\n\n[x](javascript:alert(1))\n",
      "Title",
    );
    expect(html).not.toContain("private note");
    expect(html).not.toContain("<script");
    expect(html).not.toContain("javascript:");
    expect(html).not.toContain("<h1");
  });

  it("ignores headings inside code blocks", () => {
    const { sections } = renderMarkdown("```\n## not a heading\n```\n\n## Real\n", "T");
    expect(sections).toEqual([{ heading: "Real", anchor: "real" }]);
  });
});
