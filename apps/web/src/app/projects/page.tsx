import type { Metadata } from "next";

import { ProjectIndex, type ProjectRow } from "@/components/project-index";
import { loadProjects } from "@/lib/content";

export const metadata: Metadata = { title: "Projects" };

export default function ProjectsPage() {
  const projects = loadProjects();
  const rows: ProjectRow[] = projects.map((p) => ({
    slug: p.slug,
    title: p.title,
    type: p.type,
    period: p.period,
    summary: p.summary,
    tags: Object.values(p.tags).flat(),
  }));
  const types = [...new Set(projects.map((p) => p.type))].sort();
  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="font-serif text-4xl font-medium">Projects</h1>
      <p className="mt-3 max-w-[60ch] text-muted">
        Every project here is written up by Michael and approved for publication. The guide answers
        from these pages only.
      </p>
      {rows.length > 0 ? (
        <ProjectIndex rows={rows} types={types} />
      ) : (
        <p className="mt-8">No projects are published yet.</p>
      )}
    </main>
  );
}
