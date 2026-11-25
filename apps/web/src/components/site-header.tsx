import Link from "next/link";

import { CommandPalette } from "./command-palette";
import { ThemeToggle } from "./theme-toggle";
import type { PaletteItem } from "@/lib/palette";

const NAV = [
  { href: "/projects", label: "Projects" },
  { href: "/about", label: "About" },
];

export function SiteHeader({ paletteItems }: { paletteItems: PaletteItem[] }) {
  return (
    <header className="border-b border-line">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="font-serif text-xl font-medium no-underline">
          Provenance
        </Link>
        <nav aria-label="Main" className="order-3 w-full sm:order-none sm:w-auto">
          <ul className="flex gap-6 font-mono text-sm">
            {NAV.map((item) => (
              <li key={item.href}>
                <Link href={item.href} className="no-underline hover:underline">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex items-center gap-2">
          <CommandPalette items={paletteItems} />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
