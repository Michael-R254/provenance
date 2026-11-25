import { loadStarterAnswers, type StarterAnswer } from "./content";
import { renderMarkdown } from "./markdown";

/** Approved starter answers with citations checked against the published pages. */
export function starterAnswers(): Record<string, StarterAnswer> {
  return loadStarterAnswers(undefined, (p) => renderMarkdown(p.body, p.title).sections);
}
