"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useState } from "react";

import { filterItems, type PaletteItem } from "@/lib/palette";

export function CommandPalette({ items }: { items: PaletteItem[] }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const router = useRouter();
  const listId = useId();
  const results = useMemo(() => filterItems(items, query), [items, query]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((o) => !o);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function changeOpen(next: boolean) {
    setOpen(next);
    if (!next) {
      setQuery("");
      setActive(0);
    }
  }

  function go(item: PaletteItem | undefined) {
    if (!item) return;
    changeOpen(false);
    router.push(item.href);
  }

  function onInputKey(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      go(results[active]);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={changeOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="js-only flex items-center gap-2 rounded border border-line px-3 py-1.5 font-mono text-sm text-muted hover:border-accent hover:text-ink"
        >
          Search
          <kbd
            className="hidden rounded border border-line px-1 text-xs sm:inline"
            aria-hidden="true"
          >
            ⌘K
          </kbd>
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-ink/30" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed top-[12vh] left-1/2 w-[min(36rem,calc(100vw-2rem))] -translate-x-1/2 rounded border border-line bg-surface shadow-lg"
        >
          <Dialog.Title className="sr-only">Search the site</Dialog.Title>
          <input
            autoFocus
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={results[active] ? `${listId}-${active}` : undefined}
            aria-label="Search pages, projects and sections"
            placeholder="Search pages, projects and sections"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={onInputKey}
            className="w-full border-b border-line bg-transparent px-4 py-3 outline-none focus-visible:outline-none"
          />
          <ul
            id={listId}
            role="listbox"
            aria-label="Results"
            className="max-h-80 overflow-y-auto py-2"
          >
            {results.length === 0 && (
              <li
                role="option"
                aria-selected="false"
                aria-disabled="true"
                className="px-4 py-2 text-muted"
              >
                No matches
              </li>
            )}
            {results.map((item, i) => (
              <li
                key={item.href}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseMove={() => setActive(i)}
                onClick={() => go(item)}
                className={`flex cursor-pointer items-baseline justify-between gap-4 px-4 py-2 ${
                  i === active ? "bg-accent-soft" : ""
                }`}
              >
                <span>{item.label}</span>
                <span className="shrink-0 font-mono text-xs text-muted">
                  {item.hint ?? item.group}
                </span>
              </li>
            ))}
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
