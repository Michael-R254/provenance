import type { Metadata } from "next";

import { loadProfile } from "@/lib/content";
import { renderMarkdown } from "@/lib/markdown";

export const metadata: Metadata = { title: "About" };

export default function AboutPage() {
  const profile = loadProfile();
  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="font-serif text-4xl font-medium">About</h1>
      {profile ? (
        <div
          className="prose-field mt-6"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(profile.body, profile.title).html }}
        />
      ) : (
        <p className="mt-6 max-w-[60ch] text-muted">
          Michael&apos;s profile will appear here once he has written and approved it.
        </p>
      )}
    </main>
  );
}
