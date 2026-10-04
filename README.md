> **Плановое обновление программы 14.10.2026**
>
> Текущий релиз сохраняет проверенный рабочий контур Promotions. Используемые legacy promotion mutation endpoints Ozon имеют плановое отключение 13.10.2026; новый transport не внедрён до появления возможности подтвердить его фактическое поведение.

# Ozon Manager — текущий локальный релиз

Local Streamlit application for safe management of **Elastic Boosting `action_price`** through the audited Ozon Promotions API contract as verified for this release. The current build covers Candidates, Participants, Auto-Add, history and snapshot-backed rollback workflows.

## Scope

The current build manages:

- Elastic Boosting candidates → participant ADD;
- existing participant `action_price` UPDATE;
- participant REMOVE;
- read-only Auto-Add inspection and threshold-based deletion;
- Auto-Add rollback;
- operation history, reconciliation and snapshot-based rollback.

The only participant price mutation target is `action_price`. Base product price is never mutated.

**Blocked:** Target Boost input/formula, base-price mutation, Seller Actions, undocumented activate/deactivate update workarounds, blind mutation retries.

## Safety workflow

```text
Load Promotion
→ Load Participants
→ Select Products
→ Read Current State
→ Preview
→ Fresh Check
→ Snapshot
→ Explicit Confirmation
→ Mutation
→ Read After Write
→ Per-SKU Verification
→ Result
→ History
```

No mutation is allowed without Preview, Fresh Check, Snapshot and explicit Confirmation. Rollback is itself a mutation and follows the same safety gates.

For Participant UPDATE, the UI calculates an individual Elastic Boosting discount interval from the current Ozon `price_min_elastic` / `price_max_elastic` values. There is no fixed `1%–18%` UPDATE rule. The **Единый процент для всех выбранных товаров** control can apply one manually entered percentage to the whole package only when every selected product passes its own minimum and maximum range; if any product fails, the package is not changed.

All long-running reads, Fresh Checks, snapshot creation, mutations and read-after-write verification use a centered modal loading overlay with step-by-step status.

## API contract used by the code

From API_SPEC_v1.6:

- `GET /v1/actions` — promotion listing;
- `POST /v2/actions/candidates` — candidate read (cursor `last_id`);
- `POST /v2/actions/products` — participant read (cursor `last_id`);
- `POST /v1/actions/products/activate` — live-verified action-price mutation for an existing Elastic Boosting participant;
- `POST /v2/actions/products` — participant read and read-after-write verification.

The adapter uses the reconciled current contract: `GET /v1/actions`, `POST /v2/actions/candidates`, `POST /v2/actions/products`, `POST /v1/actions/products/activate`, and `POST /v1/actions/products/deactivate`.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app/ui/streamlit_app.py
```

Product-card name/SKU enrichment uses an application-level batch setting:

```text
OZON_PRODUCT_INFO_BATCH_SIZE=1000
```

This value controls local request batching; it is not treated as a new Ozon API limit by the application.

For development/testing without real Ozon mutation, use the mock adapter through the test suite. The runtime UI does not expose a Mock mode.



## Tests

```bash
pytest
python -m compileall -q app tests
```

Current local verification for this build: **256 passed, 1 skipped** in the full Python suite. The single skip is the Streamlit smoke test when Streamlit is not installed in the test environment. JavaScript syntax for the custom table component is checked separately with `node --check` on the extracted component script.

Current automated suite covers:

- state machine;
- action_price validation;
- Target Boost blocking;
- Preview/Fresh Check/Snapshot/Confirmation gate;
- successful mutation + verification;
- partial rejection;
- verification mismatch;
- timeout/unknown result without blind retry;
- immutable snapshot fields;
- 1/10/100/1000 bulk planning/preview;
- snapshot-based rollback;
- adapter wire contract;
- security fixture scan.

## Security

Credentials are read from environment variables or Streamlit secrets and are never written to SQLite/history/snapshots/logs. `.env` and local database/log files are ignored by Git.

## Known limitation

Ozon-specific action-price precision/tick/rounding is not invented by this application. The adapter transports decimal amounts as strings; validation beyond positivity is deliberately conservative until a verified Ozon rule is available.


## Current safety-audit status

- Real Ozon `action_price` mutation: **LIVE VERIFIED** through `POST /v1/actions/products/activate` on an existing Elastic Boosting participant; restore was also verified.
- Mutation batching: controlled by `Settings.batch_size` / `OZON_BATCH_SIZE`; this is an application configuration value, not an asserted Ozon API limit.
- Mutation transport status: taken from the adapter result; no hardcoded HTTP 200 is used.
- Timeout/network ambiguity: classified as `UNKNOWN_RESULT`; no blind retry is performed.
- Pre-mutation Fresh Check read failure: persisted as a mutation-blocking error and aborts before any mutation call.
- 900-SKU mock mutation stress scenario: covered by automated tests; no real Ozon mutation is performed.
- Auto-Add rollback: confirmed in controlled project verification; six test SKUs reached `CONFIRMED_RESTORED`.

## Current mutation contract

`POST /v1/actions/products/update` is **not used**. The adapter's `update_products()` method intentionally routes existing-participant price UPDATE through the live-verified `POST /v1/actions/products/activate` contract. It accepts `action_id` plus `products[{product_id, action_price, stock?}]` and returns accepted/rejected results. The workflow preserves partial results and performs mandatory read-after-write verification.

Candidate ADD uses the same activate transport with its own Fresh Check and per-product Elastic Boosting price-range validation.
## Текущий статус релиза — 04.10.2026

- Локальный режим: **single-user**.
- Полный Python regression suite: **256 passed, 1 skipped**.
- `python -m compileall -q app tests`: **PASS**.
- Credentials/runtime secrets are not included in the release archive.
- Preview, Fresh Check, Snapshot-before-mutation, Confirmation, read-after-write verification, partial-result handling, fail-closed `UNKNOWN_RESULT`, History and snapshot-backed rollback остаются частью текущего safety workflow.
- Stocks и Auto-Add работают в пределах описанного в документации текущего контракта.
- **Известный плановый риск:** promotion mutation endpoints `POST /v1/actions/products/activate` и `POST /v1/actions/products/deactivate` подтверждены для текущего релиза, но в актуальном API snapshot имеют shutdown **13.10.2026**. Замена не считается реализованной, пока не подтверждена актуальным контрактом и фактическим поведением Ozon.

## Запуск в один клик (Windows)

Для запуска без PowerShell и ручного ввода команд дважды щёлкните **START_OZON_MANAGER.vbs**.
Первый запуск создаст `.venv` и установит зависимости; последующие запуски используют готовое окружение.
Для остановки приложения используйте **STOP_OZON_MANAGER.bat**.

Подробнее: `LAUNCHER_README_RU.md`.


## Current UI contract

- Candidates, Participants and Auto-Add use the shared interactive table component.
- Tables support horizontal scrolling, fixed-height table frames, sticky headers, sorting, right-click header filtering, Shift+LMB / Shift+RMB range selection and header `✓` select-all for selectable tables.
- Participants UPDATE exposes per-product minimum/maximum Elastic Boosting thresholds and a global percentage control.
- ADD/UPDATE result screens remain visible after mutation until the user closes them.
- Long-running operations display a centered modal loading overlay instead of only an inline page status.

## UI verification

The project uses `Streamlit AppTest` for application-level UI/startup verification. A real-browser Playwright E2E layer is intentionally not part of the release or development test stack: the previous browser harness was environment/lifecycle-sensitive and did not provide a reliable release signal.

Run:

```bash
pytest
```

This includes the Streamlit AppTest smoke contract and the application/domain/integration/contract/security suites.
