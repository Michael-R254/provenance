import type { Metadata, Viewport } from "next";

import { newsreader, plexMono, plexSans } from "./fonts";
import "./globals.css";
import { SiteHeader } from "@/components/site-header";
import { loadProjects } from "@/lib/content";
import { renderMarkdown } from "@/lib/markdown";
import type { PaletteItem } from "@/lib/palette";

export const metadata: Metadata = {
  title: { default: "Provenance", template: "%s · Provenance" },
  description: "An AI guide to Michael Rollinson's engineering work, with cited evidence.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f4f1e8" },
    { media: "(prefers-color-scheme: dark)", color: "#111712" },
  ],
};

// Runs before paint: applies a saved theme and marks that JavaScript is available.
const HEAD_SCRIPT = `(function(){var d=document.documentElement;d.classList.remove("no-js");try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")d.dataset.theme=t}catch(e){}})()`;

function paletteItems(): PaletteItem[] {
  const pages: PaletteItem[] = [
    { label: "Home", href: "/", group: "Pages" },
    { label: "Ask the guide", href: "/ask", group: "Pages", keywords: "chat question" },
    { label: "Projects", href: "/projects", group: "Pages" },
    { label: "About", href: "/about", group: "Pages" },
  ];
  const projects = loadProjects();
  const projectItems = projects.map<PaletteItem>((p) => ({
    label: p.title,
    href: `/projects/${p.slug}`,
    group: "Projects",
    hint: p.type,
    keywords: [p.summary, ...Object.values(p.tags).flat()].join(" "),
  }));
  const sections = projects.flatMap((p) =>
    renderMarkdown(p.body, p.title).sections.map<PaletteItem>((s) => ({
      label: s.heading,
      href: `/projects/${p.slug}#${s.anchor}`,
      group: "Sections",
      hint: p.title,
    })),
  );
  return [...pages, ...projectItems, ...sections];
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en-GB"
      className={`no-js ${newsreader.variable} ${plexSans.variable} ${plexMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: HEAD_SCRIPT }} />
        <style>{`.no-js .js-only{display:none!important}`}</style>
      </head>
      <body className="flex min-h-screen flex-col bg-paper text-ink antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:bg-surface focus:p-3"
        >
          Skip to content
        </a>
        <SiteHeader paletteItems={paletteItems()} />
        <div className="flex-1">{children}</div>
        <footer className="border-t border-line">
          <div className="mx-auto max-w-6xl px-4 py-6 font-mono text-xs text-muted sm:px-6">
            Answers and pages come only from write-ups Michael has approved for publication.
          </div>
        </footer>
      </body>
    </html>
  );
}
