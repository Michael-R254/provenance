import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { AnchorRegistry } from "./anchors";

type Case = { title: string; headings: string[]; anchors: string[] };
const vectors = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, "../../../../ingest/tests/fixtures/anchor-vectors.json"),
    "utf8",
  ),
) as { cases: Case[] };

describe("anchors match the ingestion pipeline", () => {
  for (const c of vectors.cases) {
    it(c.title, () => {
      const registry = new AnchorRegistry();
      expect([c.title, ...c.headings].map((h) => registry.anchorFor(h))).toEqual(c.anchors);
    });
  }
});
