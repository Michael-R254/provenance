/**
 * Heading anchors. Must match ingest/src/ingest/anchors.py exactly, because citations link to
 * these ids. Shared test vectors: ingest/tests/fixtures/anchor-vectors.json.
 */

const STRIP = /[^\p{L}\p{N}_\- ]/gu;

export function slugify(heading: string): string {
  return heading.trim().toLowerCase().replace(STRIP, "").replaceAll(" ", "-");
}

export class AnchorRegistry {
  private seen = new Map<string, number>();

  anchorFor(heading: string): string {
    const base = slugify(heading);
    const count = this.seen.get(base) ?? 0;
    this.seen.set(base, count + 1);
    return count === 0 ? base : `${base}-${count}`;
  }
}
