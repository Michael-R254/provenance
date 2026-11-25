"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function effectiveTheme(): Theme {
  const set = document.documentElement.dataset.theme;
  if (set === "light" || set === "dark") return set;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    // Read the theme the inline head script applied before paint.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(effectiveTheme());
  }, []);

  const next: Theme = theme === "dark" ? "light" : "dark";

  function toggle() {
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {
      // Private mode: the choice lasts for this page only.
    }
    setTheme(next);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="js-only rounded border border-line px-3 py-1.5 font-mono text-sm hover:border-accent"
      aria-label={theme ? `Switch to ${next} theme` : "Switch theme"}
    >
      <span aria-hidden="true">{theme === "dark" ? "Light" : theme ? "Dark" : "Theme"}</span>
    </button>
  );
}
