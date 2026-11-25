import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { loadProject, loadProjects, TAG_LABELS, type TagField } from "@/lib/content";
import { renderMarkdown } from "@/lib/markdown";

// Cache Components needs at least one param; the placeholder renders the 404 page.
const PLACEHOLDER = "__none__";

export function generateStaticParams() {
  const slugs = loadProjects().map((p) => ({ slug: p.slug }));
  return slugs.length > 0 ? slugs : [{ slug: PLACEHOLDER }];
}

export async function generateMetadata({
  params,
}: PageProps<"/projects/[slug]">): Promise<Metadata> {
  const project = loadProject((await params).slug);
  return project ? { title: project.title, description: project.summary } : {};
}

export default async function ProjectPage({ params }: PageProps<"/projects/[slug]">) {
  const project = loadProject((await params).slug);
  if (!project) notFound();
  const { html, sections, introAnchor } = renderMarkdown(project.body, project.title);
  const meta = [project.type, project.period, project.organisation, project.role].filter(Boolean);
  const tagGroups = (Object.entries(project.tags) as [TagField, string[]][]).filter(
    ([, values]) => values.length > 0,
  );

  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <nav aria-label="Breadcrumb" className="font-mono text-sm">
        <Link href="/projects" className="text-muted underline">
          Projects
        </Link>
      </nav>
      <div className="mt-6 grid gap-12 lg:grid-cols-[minmax(0,1fr)_16rem]">
        <article aria-labelledby={introAnchor}>
          <header>
            <p className="font-mono text-sm text-muted">{meta.join(" · ")}</p>
            <h1 id={introAnchor} className="mt-2 font-serif text-4xl leading-tight font-medium">
              {project.title}
            </h1>
            <p className="mt-4 max-w-[60ch] text-lg">{project.summary}</p>
            <p className="mt-6">
              <Link
                href={`/ask?project=${project.slug}`}
                className="inline-block rounded bg-accent px-4 py-2 text-accent-ink no-underline"
              >
                Ask about this project
              </Link>
            </p>
          </header>
          <div className="prose-field mt-8" dangerouslySetInnerHTML={{ __html: html }} />
        </article>
        <aside className="space-y-8 font-mono text-sm lg:sticky lg:top-6 lg:self-start">
          {sections.length > 0 && (
            <nav aria-label="On this page">
              <h2 className="text-xs text-muted uppercase">On this page</h2>
              <ul className="mt-2 space-y-1">
                {sections.map((s) => (
                  <li key={s.anchor}>
                    <a href={`#${s.anchor}`} className="no-underline hover:underline">
                      {s.heading}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          )}
          {(tagGroups.length > 0 || project.repo) && (
            <section aria-label="Details">
              <dl className="space-y-3">
                {tagGroups.map(([field, values]) => (
                  <div key={field}>
                    <dt className="text-xs text-muted uppercase">{TAG_LABELS[field]}</dt>
                    <dd>{values.join(", ")}</dd>
                  </div>
                ))}
                {project.repo && (
                  <div>
                    <dt className="text-xs text-muted uppercase">Code</dt>
                    <dd>
                      <a href={project.repo} className="underline" rel="noopener">
                        Repository
                      </a>
                    </dd>
                  </div>
                )}
                <div>
                  <dt className="text-xs text-muted uppercase">Updated</dt>
                  <dd>
                    <time dateTime={project.updated}>{project.updated}</time>
                  </dd>
                </div>
              </dl>
            </section>
          )}
        </aside>
      </div>
    </main>
  );
}
