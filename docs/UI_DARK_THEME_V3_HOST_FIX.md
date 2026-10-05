# UI Dark Theme V3 — host readability fix

Date: 2026-10-05

## Scope

Presentation-only correction based on supplied dark-mode screenshots. The custom operational table already rendered correctly; the defect was in the host Streamlit layer around it.

## Root cause

The project CSS applied a global `.stApp { color: var(--oz-text); }` rule. `--oz-text` depended on undocumented host CSS variable names and could fall back to the light value `#070707`. In dark mode, Markdown, headings, captions and other elements that inherit their foreground color therefore became nearly black on `#0B121A`.

A second visible defect was the sticky shutdown area in the sidebar receiving a light surface through the same fallback mechanism.

## Fix

- Removed global host foreground override.
- Native Streamlit background, Markdown, headings, captions, labels, metrics, buttons and disabled states are now owned by Streamlit's active light/dark theme.
- Project-owned `oz-brand`, `oz-page-title` and `oz-page-subtitle` inherit the active host foreground instead of using private Streamlit CSS variables.
- Sidebar shutdown wrapper is transparent, eliminating the white strip in dark mode.
- Custom table component was intentionally not redesigned; its existing dark palette remains unchanged.
- Runtime `st.context.theme.type` is retained only for project-owned surfaces such as the custom loading overlay and project tokens, not to repaint native Streamlit text.

## Safety boundary

No API adapter, domain model, repository, price engine, mutation service, Fresh Check, Snapshot, reconciliation or rollback code was changed.

## Verification

- Python compileall: pass.
- JavaScript syntax for the table component: pass.
- Pytest: 270 collected; all executed tests pass with the existing environment-dependent Streamlit smoke test skipped.
- Regression tests assert that the host layer no longer overrides native Markdown/caption/button colors and no `.stApp` foreground override remains.

## Runtime note

A full visual browser verification must be performed on the Windows runtime where Streamlit is installed. Restart the Streamlit process after replacing the project so `.streamlit/config.toml` and Python UI code are reloaded.
