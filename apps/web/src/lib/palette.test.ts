import { describe, expect, it } from "vitest";

import { filterItems, type PaletteItem } from "./palette";

const items: PaletteItem[] = [
  { label: "Projects", href: "/projects", group: "Pages" },
  { label: "Example Widget Sorter", href: "/projects/a", group: "Projects", keywords: "python" },
  {
    label: "Results",
    href: "/projects/a#results",
    group: "Sections",
    hint: "Example Widget Sorter",
  },
];

describe("filterItems", () => {
  it("matches every word across label, hint and keywords", () => {
    expect(filterItems(items, "widget results").map((i) => i.href)).toEqual([
      "/projects/a#results",
    ]);
    expect(filterItems(items, "PYTHON").map((i) => i.href)).toEqual(["/projects/a"]);
  });

  it("returns everything (up to the limit) for an empty query", () => {
    expect(filterItems(items, "  ")).toHaveLength(3);
    expect(filterItems(items, "", 2)).toHaveLength(2);
  });
});
