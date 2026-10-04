# Current Release Audit — 2026-10-04

## Disposition

**Current local release: usable for one local user within the documented scope.** No code changes are included in this documentation release.

### Verification completed

- Full `pytest -q`: **256 passed, 1 skipped**.
- `python -m compileall -q app tests`: **PASS**.
- Release tree reviewed for credentials/runtime database/log artifacts before packaging.
- Current UI, safety workflow, Stocks, Auto-Add, History and rollback documentation reconciled with the current source tree.

### Known planned compatibility risk

The current adapter uses the live-verified legacy promotion mutation endpoints:

- `POST /v1/actions/products/activate`
- `POST /v1/actions/products/deactivate`

The bundled Ozon API reference records a planned shutdown on **2026-10-13**. The project intentionally does **not** claim a replacement is implemented or verified. This is the reason for the prominent planned update date **14.10.2026** in the README.

### Not changed

- No Python/application code was changed in this documentation update.
- No database schema was changed.
- No API transport was replaced.
- Historical audit sections below remain intact for traceability.

---


## Current addendum — History consolidation

- Common `История` page is now the single UI entry point for operation history.
- `Остатки` and `Акции` are separate modal views opened from that page.
- Stock history includes operation summary, item-level results, snapshot reference and rollback preparation.
- Promotion history retains reconciliation, Auto-Add rollback and promotion rollback.
- Duplicate stock history controls were removed from the Stocks screen.
- Full pytest regression: PASS.
- `python -m compileall -q app tests`: PASS.
- Credential-value scan: PASS.
- This patch does not constitute final RELEASE READY by itself; clean installation and final integrated audit remain required.
# Current Release Audit Addendum — 2026-10-03

## Combined forensic + security + QA disposition

This addendum supersedes stale release-gate statements in older historical sections where they conflict with the current build. Historical records are retained below for traceability.

### Confirmed

- Core non-browser QA suites are the release test surface.
- Preview, Fresh Check, Snapshot-before-mutation, Confirmation, read-after-write verification and fail-closed unknown-result handling are covered by automated tests.
- Standard rollback is snapshot-backed and Fresh-Check protected.
- Auto-Add and Auto-Add rollback are confirmed; the controlled rollback result restored six test SKUs as `CONFIRMED_RESTORED`.
- 900-SKU mock mutation stress coverage exists and performs no real Ozon mutation.
- Credentials are not intended to be persisted in SQLite/history/snapshots/logs.

### Current 2026-10-03 UI/UX verification

- Participant UPDATE global percentage control is implemented with per-product minimum/maximum Elastic validation.
- Global percentage application is all-or-nothing at the UI plan level.
- The obsolete fixed `1%–18%` Participant UPDATE rule is not present in the current dialog logic.
- Centered loading overlay is wired into the current long-running read/check/mutation paths.
- Interactive table select-all and Shift-range behavior remains covered by existing component contracts.
- Current full Python suite: **256 passed, 1 skipped**.
- `python -m compileall -q app tests`: PASS.
- Custom table component JavaScript extracted and checked with `node --check`: PASS.

### Findings fixed by this patch

- Removed the Playwright/browser E2E layer, its setup scripts, dependencies, pytest marker and release documentation.
- Logging is now configured explicitly at the actual Streamlit entrypoint with an idempotent `FileHandler`, so `logs/app.log` does not depend on `logging.basicConfig()` winning a root-logger race.
- Product-name batching documentation now clearly describes `OZON_PRODUCT_INFO_BATCH_SIZE=1000` as an application-level setting, not an Ozon API limit.
- Auto-Add rollback documentation now reflects the confirmed `CONFIRMED_RESTORED` result.

### Remaining release gates

- Controlled live release verification remains an operational gate when a real-account mutation is intentionally performed.
- Clean-install verification on the target Windows environment remains separate from the repository test run.
- Final release decision still requires the full project release checklist, not only this UI patch.

# Historical Release Audit — 2026-10-01

## Baseline
- Source archive: Ozon-Manager-phase4c-hardened.zip.
- Real authenticated Ozon mutation was not executed.
- Current automated suite: 35 tests.

## Changes
- Reconciled the current Ozon Promotions read contract to `/v2/actions/candidates` and `/v2/actions/products`.
- Implemented the live-verified `POST /v1/actions/products/activate` action-price mutation path; `/v1/actions/products/update` is not used.
- `action_price` is serialized as a money object with `amount` and `currency`.
- Mutation response categories are preserved: active, deactivated, rejected, warnings.
- Optional `stock` preserves omitted-versus-zero semantics.
- Mutation batch validation enforces the reviewed 1–1000 operation boundary.
- Fresh Check no longer invents membership/availability fields absent from the current v2 participant schema.
- Existing Preview, Snapshot, Confirmation, pre-mutation Fresh Check, no-blind-retry, verification and rollback safeguards remain active.

## Verification
- `pytest -q`: PASS — 35 tests.
- `python -m compileall -q app tests`: PASS.
- 900-SKU mock mutation: PASS, 9 batches of 100, no real Ozon request.
- Credential scan: no real credentials found in the release tree.
- `.env` is not included.

## Historical production mutation status
At that time the mutation transport was verified but the later controlled live participant UPDATE evidence had not yet been captured. This section is historical and is superseded by the current release addendum above.
## Mutation Safety QA — 2026-10-01

- Automated mutation safety suite: **72 tests passed**.
- Snapshot linkage persistence defect found and fixed.
- Fail-closed behavior verified for unknown mutation outcomes, including a mock case where state changes before the transport error.
- No blind mutation retry is permitted after an unknown result.
- Rollback is verified as a separate snapshot-backed mutation with Fresh Check and Confirmation.
- No authenticated live Ozon mutation was executed.

**Release status:** mutation safety logic is READY for a controlled live probe, but the project is not yet declared production mutation release-ready until the live probe and subsequent read-after-write verification are completed.

## Current Stocks Combined Patch — 2026-10-03 / 02B

### Checked

- Stocks mutation safety boundary;
- persisted snapshot requirement;
- duplicate execution protection;
- multi-batch partial/429 behavior;
- 900-record service-level stress with nine 100-item batches;
- rollback preparation from History;
- UNKNOWN_RESULT UI state;
- credentials/runtime-file hygiene;
- full Python regression and compile check.

### Confirmed

- Current suite: **234 tests passed, 1 skipped** where the existing Streamlit smoke test is environment-dependent.
- `python -m compileall -q app tests`: PASS.
- Terminal stock operations cannot be executed twice.
- Missing/mismatched snapshots block mutation.
- A second-batch 429 does not trigger a blind retry of an accepted first batch.
- 900 records complete through nine 100-item batches in the mock/service stress path.
- Rollback can be prepared directly from Stocks History and remains snapshot-backed.
- UNKNOWN_RESULT is represented explicitly in the UI rather than as SUCCESS.
- No real credentials are present in the release tree; `.env`, Streamlit secrets and runtime logs are absent.

### Not claimed

- No live 429/timeout/partial-failure injection was performed against Ozon.
- No undocumented Ozon retry guarantee is assumed.
- The reviewed third-party observations about rate/window limits remain audit evidence, not application retry constants.
- Clean-install verification on the user's Windows machine remains an operational release step.

### Status

Stocks Mutation QA 02B: **PASS**.
Stocks as a whole: **not yet RELEASE READY** until the final clean-install and final integrated release audit are completed.

## FIX4 Verification — 2026-10-03

### Checked
- Stocks History rollback source selection.
- Auto-Add Rollback dialog dispatch.
- Shared table filter input state/autocomplete behavior.
- Startup Account dialog behavior.

### Confirmed
- Stocks rollback candidates are filtered to `SUCCESS` operations with a snapshot.
- Pending Auto-Add rollback is consumed before History modal dispatch, so only one dialog is opened in that script run.
- Filter popup opens with an empty input and browser autocomplete/history is disabled.
- Account dialog has a one-shot startup flag and is dispatched through the existing dialog dispatcher.

### QA
- `pytest -q`: PASS — 247 tests.
- `python -m compileall -q app tests`: PASS.
- Credential-value scan: PASS; no credential values found in source.
- Runtime/cache directories removed before packaging.

### Remaining
- Clean installation on a separate Windows environment is still not independently verified in this patch.
- Real Ozon mutation for Auto-Add Rollback remains a production/live operation and was not performed by this patch.


## UI audit — 2026-10-03

- Проверены рабочие вкладки: «Акции», «Остатки», «История», а также диалоги аккаунта, кандидатов, участников, автодобавления, подтверждений операций и откатов.
- UI-таблицы используют общий компонент с вертикальной/горизонтальной прокруткой, сортировкой, фильтрацией и выбором.
- Рабочая область и поверхности приведены к токенам дизайн-системы: `1216px`, `24px`, радиус таблиц `16px`, радиус диалогов `20px`.
- `Mock mode` удалён из runtime UI; mock-адаптеры остаются только тестовой инфраструктурой.
- Для «Остатков» выбор строки больше не вызывает промежуточный rerun, поэтому «Новое наличие для выбранных» отображается сразу.
- Полный pytest: PASS.

## FIX — History Promotions regression (2026-10-03)

**Проблема:** окно «История → Акции» завершалось `IndexError: No item with that key` при обращении UI к `product_count`.

**Причина:** таблица `operations` хранит метаданные операции, а агрегаты по товарам находятся в `operation_items`. UI ошибочно ожидал агрегаты как физические колонки `operations`.

**Исправление:** `SQLiteRepository.list_operations()` возвращает `product_count`, `success_count`, `failed_count` как вычисляемые поля через `LEFT JOIN` и агрегирование `operation_items`.

**Совместимость:** существующие SQLite-базы поддерживаются без миграции.

**QA:** полный pytest и `python -m compileall -q app tests` проходят.
