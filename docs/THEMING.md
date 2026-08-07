# Theming Sprucer

Default look lives in `web/app/theme.css` (CSS variables) and `web/app/globals.css` (layout).

## Quick rebrand

1. Edit `web/public/theme.override.css` (loaded after the default theme).
2. Override any `:root` variables, for example:

```css
:root {
  --accent: #245b8a;
  --accent-bright: #3d7eb5;
  --accent-deep: #163955;
  --mist: #dde6ef;
  --paper: #f2f5f8;
  --font-display: "Your Display Font", serif;
}
```

3. Hard-refresh the browser.

You can also point a reverse proxy at your own CSS and leave `theme.override.css` empty.

## What not to fight

Component class names (`.panel`, `.btn`, `.hero`) are stable enough for light overrides. Prefer variables first so spacing and motion stay coherent.
