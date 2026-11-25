"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

export type ProjectRow = {
  slug: string;
  title: string;
  type: string;
  period?: string;
  summary: string;
  tags: string[];
};

/** A filterable table. The full table renders on the server, so it works without JavaScript. */
export function ProjectIndex({ rows, types }: { rows: ProjectRow[]; types: string[] }) {
  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const shown = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    return rows.filter((row) => {
      if (type && row.type !== type) return false;
      const text = `${row.title} ${row.summary} ${row.tags.join(" ")}`.toLowerCase();
      return words.every((w) => text.includes(w));
    });
  }, [rows, query, type]);

  return (
    <>
      <div className="js-only mt-8 flex flex-wrap items-end gap-4" role="search">
        <label className="flex flex-col gap-1 font-mono text-sm">
          Filter
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Title, summary or tag"
            className="w-72 max-w-full rounded border border-line bg-surface px-3 py-2 font-sans"
          />
        </label>
        <label className="flex flex-col gap-1 font-mono text-sm">
          Type
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="rounded border border-line bg-surface px-3 py-2 font-sans"
          >
            <option value="">All types</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <p className="font-mono text-sm text-muted" aria-live="polite">
          {shown.length} of {rows.length} shown
        </p>
      </div>
      <table className="mt-6 w-full border-collapse text-left">
        <caption className="sr-only">Published projects</caption>
        <thead className="font-mono text-xs text-muted uppercase">
          <tr className="border-b border-line">
            <th scope="col" className="py-2 pr-4 font-normal">
              Project
            </th>
            <th scope="col" className="hidden py-2 pr-4 font-normal sm:table-cell">
              Type
            </th>
            <th scope="col" className="hidden py-2 font-normal md:table-cell">
              Period
            </th>
          </tr>
        </thead>
        <tbody>
          {shown.map((row) => (
            <tr key={row.slug} className="border-b border-line align-top">
              <td className="py-4 pr-4">
                <Link href={`/projects/${row.slug}`} className="font-serif text-xl underline">
                  {row.title}
                </Link>
                <p className="mt-1 max-w-[65ch] text-muted">{row.summary}</p>
                <p className="mt-1 font-mono text-xs text-muted sm:hidden">
                  {row.type}
                  {row.period ? ` · ${row.period}` : ""}
                </p>
              </td>
              <td className="hidden py-4 pr-4 font-mono text-sm sm:table-cell">{row.type}</td>
              <td className="hidden py-4 font-mono text-sm md:table-cell">{row.period ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
