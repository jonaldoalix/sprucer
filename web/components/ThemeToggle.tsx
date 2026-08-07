"use client";

import { useEffect, useState } from "react";

/** Stored preference: explicit theme or follow OS. */
export type ThemePreference = "system" | "light" | "neutral" | "dark";
/** Resolved theme applied to <html data-theme>. */
export type SprucerTheme = "light" | "neutral" | "dark";

const OPTIONS: { id: ThemePreference; label: string }[] = [
  { id: "system", label: "System" },
  { id: "light", label: "Light" },
  { id: "neutral", label: "Neutral" },
  { id: "dark", label: "Dark" },
];

const STORAGE_KEY = "sprucer-theme";

function systemTheme(): SprucerTheme {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function resolveTheme(pref: ThemePreference): SprucerTheme {
  return pref === "system" ? systemTheme() : pref;
}

function readPreference(): ThemePreference {
  if (typeof document === "undefined") return "system";
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "system" || stored === "light" || stored === "neutral" || stored === "dark") {
      return stored;
    }
  } catch {
    // ignore
  }
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "neutral" || attr === "dark" || attr === "light") return attr;
  return "system";
}

function applyPreference(pref: ThemePreference) {
  const resolved = resolveTheme(pref);
  document.documentElement.setAttribute("data-theme", resolved);
  document.documentElement.setAttribute("data-theme-pref", pref);
  try {
    localStorage.setItem(STORAGE_KEY, pref);
  } catch {
    // ignore private-mode / blocked storage
  }
}

/** Compact theme select — System follows OS; choice persists in localStorage. */
export function ThemeToggle() {
  const [pref, setPref] = useState<ThemePreference>("system");

  useEffect(() => {
    const current = readPreference();
    setPref(current);
    applyPreference(current);

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      const latest = readPreference();
      if (latest === "system") applyPreference("system");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  function onChange(next: ThemePreference) {
    setPref(next);
    applyPreference(next);
  }

  return (
    <label className="theme-toggle">
      <span className="sr-only">Color theme</span>
      <select
        className="theme-select"
        value={pref}
        aria-label="Color theme"
        onChange={(e) => onChange(e.target.value as ThemePreference)}
      >
        {OPTIONS.map((t) => (
          <option key={t.id} value={t.id}>
            {t.label}
          </option>
        ))}
      </select>
    </label>
  );
}
