# Theming Sprucer

Default look lives in `web/app/theme.css` (CSS variables) and `web/app/globals.css` (layout).

## Built-in modes

Set `data-theme` on `<html>` (the topbar theme select does this and persists to `localStorage`):

| Mode | Intent |
|------|--------|
| `light` | Spruce desk on pale paper (restore baseline) |
| `neutral` | Mid “lichen slate” sage-gray desk — not white, not black |
| `dark` | Low-glare night desk; primary fills stay dark enough for light `--on-accent` text |

Tag `restore-light-baseline` marks the pre-theme-experiment commit if you need to compare history (`git show restore-light-baseline`). Prefer branch/worktree workflows over resetting shared branches.

## Quick rebrand

1. Edit `web/public/theme.override.css` (loaded after the default theme).
2. Override any `:root` / `[data-theme="…"]` variables, for example:

```css
html[data-theme="light"] {
  --accent: #245b8a;
  --accent-bright: #3d7eb5;
  --accent-deep: #163955;
}
```

3. Hard-refresh the browser.

## What not to fight

Component class names (`.panel`, `.btn`, `.hero`) are stable enough for light overrides. Prefer variables first so spacing and motion stay coherent. Surfaces that used to hard-code `white` now prefer `--surface-lift` / `--panel-solid` so dark mode stays readable.
