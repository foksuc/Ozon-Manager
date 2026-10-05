# Ozon Manager — Dark Theme V2

## Scope

UI/UX-only correction of light/dark rendering. Ozon API adapters, mutation services,
Preview/Fresh Check/Snapshot, reconciliation, rollback, repositories and business
identifiers are not changed by this patch.

## Why V1 was insufficient

The previous implementation mixed three theming layers:

1. Streamlit theme configuration;
2. custom CSS that repainted native Streamlit/BaseWeb widgets;
3. an iframe-based custom table with its own palette.

This could produce mismatched surfaces in dark mode: the main application switched
theme while individual controls, table states or overlays retained colors derived
from another layer.

## V2 approach

- Streamlit native widgets are colored by `.streamlit/config.toml` only.
- `[theme.light]`, `[theme.dark]`, `[theme.light.sidebar]` and
  `[theme.dark.sidebar]` define complete surface/text/border/semantic colors.
- Custom app CSS is restricted to layout, radii and project-owned HTML.
- The package/table iframe receives the active Streamlit theme object and applies
  a complete dark palette to table body, header, row hover, selected row, inputs,
  context filter, scrollbar and focus states.
- The iframe body is hidden until the theme render message arrives, preventing a
  white flash before dark colors are applied.
- Minimum Streamlit version is `1.51`, the release line that introduced separate
  switchable `[theme.light]` and `[theme.dark]` configuration.

## Dark palette

- workspace: `#0B121A`
- surface: `#141E29`
- elevated/table header: `#192634`
- primary text: `#F3F6FA`
- muted table text: `#A9B7C5`
- border: `#304152`
- primary action: `#276EF1`
- link/accent text: `#72A7FF`

Approximate contrast checks:

- primary text / workspace: 17.37:1
- primary text / surface: 15.53:1
- muted text / surface: 8.23:1
- link / workspace: 7.79:1
- white / primary button: 4.58:1

## Runtime note

After replacing the project files, fully stop and restart Streamlit/Ozon Manager so
`.streamlit/config.toml` is reloaded before evaluating the dark theme.
