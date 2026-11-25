export type PaletteItem = {
  label: string;
  href: string;
  group: "Pages" | "Projects" | "Sections";
  hint?: string;
  keywords?: string;
};

/** Every word of the query must appear in the label, hint or keywords. Empty query: all items. */
export function filterItems(items: PaletteItem[], query: string, limit = 12): PaletteItem[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return items.slice(0, limit);
  return items
    .filter((item) => {
      const haystack = `${item.label} ${item.hint ?? ""} ${item.keywords ?? ""}`.toLowerCase();
      return words.every((w) => haystack.includes(w));
    })
    .slice(0, limit);
}
