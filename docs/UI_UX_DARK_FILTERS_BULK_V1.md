# UI/UX Dark Theme, Table Filters & Bulk Selection — V1

## Scope

This change is presentation/UI-only. Existing Ozon API adapters, mutation services, business rules, identifiers, persistence, Preview/Fresh Check/Snapshot/reconciliation and rollback logic were not modified.

Emoji navigation icons remain intentionally enabled as a project-specific exception to the master design-system icon rule.

## Dark theme

- Added explicit Streamlit light/dark theme palettes in `.streamlit/config.toml`.
- Reworked custom CSS surfaces, text, borders, dialogs, metrics, sidebar and loading overlay to use active Streamlit theme variables instead of fixed light colors.
- The shared custom table consumes the Streamlit Component `theme` object and switches table, header, selected/hover rows, filter popover and editable inputs together with the active theme.

## Table context filters

Right-click filtering now supports:

- `Содержит`;
- `Равно`;
- `Больше или равно`;
- `Меньше или равно`.

Numeric comparison understands spaces used as thousands separators and decimal comma/dot. Percentage input is supported directly, e.g. `5%`. When a cell contains both a price and a percentage (for example `2314 ₽ · 14.30%`), a threshold entered with `%` compares the percentage part.

Existing Enter-to-apply, Esc-to-close, sorting, checkbox-only selection, Shift range selection and table scrolling behavior are preserved.

## Candidates bulk action

The Candidates dialog now contains `Добавить все товары со скидкой меньше N%`.

Candidates do not have a current participant discount. Therefore the threshold is compared with the existing Ozon-derived **minimum Elastic Boosting discount** calculated from the current product price and `price_min_elastic` — the same lower bound already used by the ADD price planner.

The button does not call Ozon and does not bypass mutation safety. It only builds `add_selected_ids` and opens the existing `Добавление товаров` workflow.

## Participants bulk action

The Participants dialog now contains `Удалить все товары со скидкой больше N%`.

The comparison uses the current participant discount calculated from base price and current action price. The button only builds `delete_selected_ids` and opens the existing deletion confirmation dialog. The existing `RemoveProductsService` remains the mutation path.

## QA

Validated:

- Python compile check for `streamlit_app.py`;
- full pytest regression suite;
- JavaScript syntax with `node --check`;
- executable filter checks for contains/equality/`>=`/`<=`, percentages, mixed price+percentage cells and thousands separators;
- TOML parsing for `.streamlit/config.toml`;
- SHA-256 identity of critical API/mutation/business files against the source archive.

Live Streamlit/browser visual verification was not available in the build environment because Streamlit is not installed there and outbound network access is disabled. BrowserAct therefore could not be installed in this environment.
