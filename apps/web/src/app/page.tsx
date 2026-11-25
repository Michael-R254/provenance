import { SiteIntro } from "@/components/site-intro";
import { loadProjects } from "@/lib/content";

export default function Home() {
  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
      <SiteIntro projectCount={loadProjects().length} />
      <section
        aria-labelledby="ask-title"
        className="mt-16 max-w-3xl rounded border border-line bg-surface p-6"
      >
        <h2 id="ask-title" className="font-serif text-2xl font-medium">
          Ask the guide
        </h2>
        <p className="mt-2 text-muted">
          The question box is on its way. Until then, the project pages hold the same evidence the
          guide will cite.
        </p>
      </section>
    </main>
  );
}
