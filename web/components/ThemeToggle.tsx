"use client";

import { useEffect, useState } from "react";

export type SprucerTheme = "light" | "neutral" | "dark";

const THEMES: { id: SprucerTheme; label: string }[] = [
  { id: "light", label: "Light" },
  { id: "neutral", label: "Neutral" },
  { id: "dark", label: "Dark" },
];

const STORAGE_KEY = "sprucer-theme";

function readTheme(): SprucerTheme {
  if (typeof document === "undefined") return "light";
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "neutral" || attr === "dark" || attr === "light") return attr;
  return "light";
}

function applyTheme(theme: SprucerTheme) {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // ignore private-mode / blocked storage
  }
}

/** Compact theme select — one control instead of three labels. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<SprucerTheme>("light");

  useEffect(() => {
    setTheme(readTheme());
  }, []);

  function onChange(next: SprucerTheme) {
    setTheme(next);
    applyTheme(next);
  }

  return (
    <label className="theme-toggle">
      <span className="sr-only">Color theme</span>
      <select
        className="theme-select"
        value={theme}
        aria-label="Color theme"
        onChange={(e) => onChange(e.target.value as SprucerTheme)}
      >
        {THEMES.map((t) => (
          <option key={t.id} value={t.id}>
            {t.label}
          </option>
        ))}
      </select>
    </label>
  );
}
