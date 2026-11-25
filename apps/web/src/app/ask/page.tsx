import type { Metadata } from "next";
import { Suspense } from "react";

import { AskView } from "./ask-view";
import { loadProjects } from "@/lib/content";
import { starterAnswers } from "@/lib/starter-answers";

export const metadata: Metadata = { title: "Ask" };

export default function AskPage() {
  const projects = loadProjects().map((p) => ({ slug: p.slug, title: p.title }));
  const answers = starterAnswers();
  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <h1 className="sr-only">Ask about Michael&apos;s work</h1>
      <Suspense fallback={null}>
        <AskView projects={projects} starterAnswers={answers} />
      </Suspense>
    </main>
  );
}
