# 2026-10-05 — Actions entry buttons + README simplification

- Кнопки «Кандидаты — N» и «Участники — N» теперь являются самостоятельными primary entry points в том же стиле, что «Автодобавление Ozon».
- Удалены промежуточные кнопки «Открыть таблицу кандидатов» и «Открыть таблицу участников»; сами существующие диалоги и их функциональность не изменены.
- Полностью переписан README: сохранён блок с изображением/бейджами, добавлено кликабельное оглавление, упрощённая установка для новичка, актуальное описание возможностей и отдельный раздел возможного будущего развития.
- API adapters, business/mutation services и persistence не изменялись.

# 2026-10-04 — Current local release / documentation reconciliation

- Полностью сверена документация с текущим исходным деревом Ozon Manager без изменения application code.
- README обновлён под текущий локальный single-user релиз.
- В самом верху README добавлена пометка: **«Плановое обновление программы 14.10.2026»**.
- Актуализированы API reconciliation, API contract, release audit и test plan.
- Исторические phase/audit записи сохранены без переписывания, чтобы не терять forensic traceability.
- Текущая автоматическая проверка: **256 passed, 1 skipped**; `compileall` — PASS.
- Зафиксирован известный плановый риск: legacy Promotions mutation endpoints `/v1/actions/products/activate` и `/v1/actions/products/deactivate` имеют shutdown 13.10.2026 по bundled API reference. Новый transport в этот релиз не придумывался и не внедрялся.


## 2026-10-03 — UI / русификация / Остатки

- Выполнен сквозной аудит UI-кода вкладок и диалоговых окон относительно `docs/OZON_SELLER_DESIGN_SYSTEM.md`.
- Рабочая область приведена к сетке `1216px` с внутренними отступами `24px`; таблицы используют оболочку с радиусом `16px`, диалоги — `20px`.
- Основные пользовательские подписи и таблицы русифицированы; внутренние API-коды и идентификаторы не изменены.
- Убран `Mock mode` из рабочего интерфейса и из runtime-конфигурации; тестовые mock-адаптеры сохранены для pytest.
- В «Остатках» выбор строки сразу показывает управление «Новое наличие для выбранных» без принудительного rerun.
- История остатков и акций переведена на пользовательские русские названия полей/статусов; внутренние статусы БД сохранены.


## 2026-10-03 — History consolidation: Stocks / Promotions

- Unified operation history under the existing `История` page.
- Added two entry points: `Остатки` and `Акции`.
- `Остатки` opens a modal containing stock operations, per-item results, snapshot IDs and snapshot-backed rollback preparation.
- `Акции` opens a modal containing promotion operation history, reconciliation, Auto-Add rollback and promotion rollback flows.
- Removed the duplicate stock-history UI from the `Остатки` page.
- Reused the existing Stocks mutation confirmation dialog and safety pipeline for rollback initiated from History.
- Added UI contract tests for the new History ownership and entry points.
- No mutation retry behavior was changed.

## 2026-10-03 — Stocks inline edit / Prepare button fix

- Fixed Stocks custom-table inline stock edit lifecycle.
- `action=stock` now updates `stocks_edit_buffer` without forcing an immediate `st.rerun()` in the same component event cycle.
- This allows `changed` to be recalculated immediately and enables `Подготовить изменение` after entering a new stock value.
- Added regression coverage for the UI contract.

## 2026-10-03 — Stocks Mutation 02A

- hardened stock read-after-write persistence;
- added stock rollback preparation from immutable snapshots;
- added mutation contract tests for 429, timeout, partial response and 100-item batching;
- added Fresh Check coverage for reserved-stock changes;
- no real Ozon mutation executed during this stage.


## 2026-10-03 — Stocks FINAL V3

- Исправлена загрузка FBS/rFBS остатков: `/v2/product/info/stocks-by-warehouse/fbs` теперь получает до 1000 `offer_id` за запрос согласно актуальной схеме, вместо одного HTTP-запроса на каждый товар.
- Сохранена cursor/`has_next` пагинация внутри каждого batch.
- Добавлен fallback для товаров без `offer_id`: получение SKU через `/v3/product/info/list` и отдельные SKU batches.
- Добавлен регрессионный тест на 1001 товар (`1000 + 1` batch).
- Акции/Elastic Boosting не изменялись.

## 2026-10-03 — Participant UPDATE global percentage + unified loading modal

- Added **Единый процент для всех выбранных товаров** to Participant UPDATE.
- Replaced predefined percentage choices with one manual percentage input.
- Global percentage application validates every selected product against its own current Elastic Boosting minimum and maximum discount range. If one product fails, the package remains unchanged.
- Kept Participant UPDATE free of the obsolete fixed `1%–18%` business rule.
- Replaced long-running inline operation status with a centered modal loading overlay for connection checks, Ozon reads, Product Card enrichment, reconciliation, rollback, REMOVE, ADD and UPDATE workflows.
- Loading modal exposes the current operation step and disappears after completion/failure; it does not replace Preview/Fresh Check/Snapshot/Confirmation/read-after-write gates.
- Updated current README and architecture/requirements/API/UI/test documentation to reflect the implemented behavior.
- Current automated verification: 256 passed, 1 skipped; Python compileall PASS; custom table JavaScript syntax PASS.


## 2026-10-03 — Ozon Elastic Boosting candidate ADD price bounds

- Candidate → participant ADD now calculates an individual minimum and maximum discount from the Ozon-returned `price_min_elastic` / `price_max_elastic` fields.
- The ADD editor displays both thresholds as `N% → price`.
- New candidates default to the minimum required discount for activation.
- Manual discount edits and the mutation service both reject prices outside the per-product Ozon interval.
- Missing or inconsistent Elastic Boosting thresholds fail closed before snapshot/mutation.
## 2026-10-03 — Forensic / Security / QA hardening

- Removed the Playwright/Chromium browser E2E layer from the project.
- Removed `tests/e2e/`, `SETUP_E2E.bat`, `scripts/run_e2e.py`, and browser-E2E documentation/dependencies.
- Kept Streamlit `AppTest` as the deterministic application-level UI smoke contract.
- Configured `logs/app.log` explicitly at Streamlit startup with an idempotent file handler.
- Corrected product-name batching documentation to distinguish application batching from Ozon API limits.
- Corrected Auto-Add rollback documentation to `CONFIRMED / PASS` based on the controlled restore result.
- Added the current combined release-audit disposition and final non-E2E release gates.


## 2026-10-03 — E2E navigation contract hardening

- Updated browser E2E navigation to locate the `Акции` sidebar button by accessible role/name, so the test remains valid when the visible label includes the navigation icon (`🎯 Акции`).
- No production business logic or Ozon API behavior changed.
- Local full-suite verification in the audit environment: 176 passed, 6 skipped, 0 failed.
## 2026-10-02 — Auto-Add discount visibility and local threshold filtering
- Added calculated `Скидка` column to the Auto-Add Ozon table.
- Calculation uses only Ozon-returned `price` and `action_price_to_auto_add`; no undocumented Ozon discount-percent field is assumed.
- Preserved negative calculated values when the Auto-Add action price is above the current price.
- Added a one-button local filter to hide rows with discount strictly greater than a user-entered threshold.
- The filter is explicitly read-only and does not call an Ozon mutation endpoint.

- Consolidated runtime and local QA dependencies into a single `requirements.txt`; removed the obsolete `requirements-dev.txt`.
- Normal Windows startup no longer checks for pytest/Playwright and never installs browser test tooling.
## 2026-10-02 — Launcher / E2E browser installation fix

- Removed automatic `playwright install chromium` from normal application startup.
- Added `SETUP_E2E.bat` for explicit one-time Playwright Chromium installation.
- Normal Ozon Manager startup no longer downloads Chromium/FFmpeg.
- E2E dependencies remain in the single `requirements.txt`.


## 2026-10-02 — Auto-Add Ozon read-only table
- Added third Actions table: «Автодобавление Ozon» alongside Candidates and Participants.
- Auto-Add date is taken from Ozon `/v1/actions` `auto_add_dates`; no date is guessed or hard-coded.
- Added paginated read of `/v1/actions/auto-add/products/list` with defensive de-duplication.
- Added API fields: Product ID, SKU, Offer ID, Name, price fields, quantities, currency and add mode.
- Reused the existing interactive table component for sorting, right-click filtering, checkbox/range selection, and text copy/select behavior.
- Auto-Add remains read-only; no mutation is exposed from this table.

## 2026-10-02 — UI table visibility fix
- Removed viewport-dependent `max-height` from the interactive table container.
- Added a safe minimum table height so 1–3 row tables remain visible.
- Added regression tests for the small-table rendering case.

## UI navigation hardening — 2026-10-02

- Promotions UI is fixed to audited Elastic Boosting action `1977747`; the promotion selector was removed.
- Main screen now exposes `Акции` and `Остатки` navigation.
- `Остатки` is explicitly marked as under development and performs no API operation.
- History, reconciliation and safe rollback were moved out of the main page into the sidebar `История` destination.
- Existing candidate/participant tables and mutation workflows remain unchanged.
- Added UI contract tests for the fixed action and navigation.

## 2026-10-01 — Ozon whole-ruble price reconciliation

- Read-after-write reconciliation now accepts a whole-RUB `ROUND_HALF_UP` read-back of the requested `action_price` as ordinary confirmed `SUCCESS`.
- No new `normalized` status is introduced.
- Example: requested `885.60` and read-back `886` are confirmed as the same price intent; for a `1080` source price this is `17.962962...%`, treated as the requested `18%` operation.
- Added regression coverage for the exact observed reconciliation case.


## 2026-10-01 — ADD mutation reconciliation hardening

- A missing participant after ADD read-after-write is now classified as `UNKNOWN_RESULT`, not as `action_price` mismatch.
- Explicit Ozon `rejected` results remain `REJECTED` with the API-provided reason.
- A participant found with an actual `action_price` different from requested is classified as a real verification mismatch.
- No automatic mutation retry is performed for ambiguous post-write results.
- Added read-only ADD reconciliation from History to confirm an ambiguous result later.
- Persisted UNKNOWN_RESULT / PRICE_MISMATCH error records in SQLite history.
- Added regression coverage for missing post-write visibility and successful later reconciliation.

## 2026-10-01 — Product card refresh fix

- Fixed Product ID → Name/SKU enrichment during `Обновить данные`.
- Moved `/v3/product/info/list` card lookup from the strict SDK response model to the raw HTTP adapter.
- Preserved `sources[].sku` mapping.
- Added batching at the currently documented 1000-identifier boundary.
- Added regression tests for 893+ products, batching, and partial responses.
- Removed duplicate participant accumulation in pagination.

# 2026-10-01 — Phase D.3 contract migration

- Live-verified `/v1/actions/products/activate` for changing `action_price` on an already participating Elastic Boosting product.
- Restored the test participant to its original `action_price=1005`.
- Removed production adapter calls to unverified `/v1/actions/products/update`.
- Preserved `result.product_ids` and `result.rejected` partial results.
- Updated ADD flow to send `action_price` in activation and verify it after write.
- Removed the unverified hard-coded 1000-product API limit.
- Full pytest suite and compile check pass.

## 2026-10-01 — Elastic Boosting UI revision

- Replaced the candidate/participant price editor controls with a single 1–18% Elastic Boosting discount slider.
- Enforced an application-side maximum discount of 18%; resulting price cannot fall below 82% of `Цена`.
- Removed `Max action price` as a calculation floor. It is displayed as `Ограничение для акций` / `Ограничение для акции` only.
- Candidate and participant tables now expose Ozon `price_min_elastic` and `price_max_elastic` when returned; missing values remain `UNKNOWN`/`—`.
- Preview/confirmation shows the current `Цена`, both Elastic bounds, and the calculated new price.
- Fresh Check blocks stale ADD/UPDATE calculations when price or returned Elastic safety fields changed; it does not invent a local price-bound rule.
- Mutation result UI now distinguishes `SUCCESS`, `PARTIAL`, and `FAILED` and displays per-product Ozon rejection reasons.
- Added participant `max_action_price` mapping from Ozon response.
- Removed custom `Закрыть` buttons; native dialog × / Esc closing is used.

## 2026-10-01 — SKU in product tables

- Product tables now display Ozon SKU instead of the internal Product ID value.
- SKU is resolved from the read-only product-info lookup and cached per Streamlit session.
- Internal mutation paths continue using the original Ozon Product ID; changing the display identifier does not alter mutation contracts.
- Candidate/participant selection maps displayed SKU back to the original Product ID before any operation.
- Added contract tests for SKU resolution and table rendering.


## 2026-10-01 — Mutation Safety QA

- Added mutation safety regression suite covering Preview, Fresh Check, Snapshot, Confirmation, pre-mutation Fresh Check, partial failures, read-after-write mismatch, unknown mutation results, duplicate fingerprints, and rollback.
- Fixed durable snapshot linkage so `snapshot_id` and `SNAPSHOTTED` status are persisted immediately after snapshot creation.
- Added fail-closed mock scenario where mutation changes state before returning `UNKNOWN_RESULT`; blind retry remains blocked.
- Automated suite: 72 passed.

## 2026-10-01 — One-click launcher icon

- Added the supplied Streamlit mark as `assets/ozon_manager.png`.
- Added multi-resolution Windows icon `assets/ozon_manager.ico`.
- Streamlit browser page now uses the supplied mark as `page_icon`.
- Added `INSTALL_OZON_MANAGER.vbs` to create a desktop `Ozon Manager.lnk` with the supplied icon.
- No Ozon API mutation behavior changed.

## 2026-10-01 — Phase 4C runtime/UI hardening

- Added explicit `action_type=ELASTIC_BOOSTING` recognition in promotion validation.
- Added cursor-complete candidate loading through the existing `/v2/actions/candidates` contract.
- When an Elastic promotion has zero participants, the Streamlit UI now shows candidate products instead of terminating the screen.
- Candidate products are informational only; they are never silently promoted to mutation targets.
- Mutation remains gated on participant presence, Preview, Fresh Check, Snapshot and Confirmation.
- Added adapter and validator regression tests.
# Changelog
- Candidate ADD price selection now uses per-product Ozon `price_min_elastic` / `price_max_elastic` thresholds. The UI calculates and displays the minimum and maximum required discount percentages and target prices, defaults new candidates to the minimum required discount, and blocks ADD outside the returned price interval.


## Phase 3 — Core Development

- implemented domain models and operation state machine;
- implemented SQLite history/snapshot/error persistence;
- implemented Ozon Promotions adapter;
- implemented mock adapter;
- implemented Preview/Fresh Check/Snapshot/Confirmation/Mutation/Verification workflow;
- implemented partial-result classification;
- implemented unknown-outcome handling without blind retry;
- implemented Snapshot-based rollback service and UI flow;
- added automated tests;
- added Streamlit MVP UI;
- explicitly blocked Target Boost and base-price mutation.

### Known contract issue

The Phase 3 request mentions `POST /v2/actions` for promotion listing, while approved API_SPEC_v1.6 specifies `GET /v1/actions`. The implementation follows v1.6 and does not invent the conflicting endpoint.

## 2026-10-01 — API Contract Reconciliation

- Reconciled Promos read responses to the top-level `result` envelope.
- Fixed `/v1/actions` promotion parsing.
- Fixed `/v1/actions/products` pagination and participant parsing.
- Removed use of unverified `/v2/actions/products` for read-after-write; verification now re-reads the verified participant endpoint.
- Disabled real `action_price` mutation in the Ozon adapter because `/v1/actions/products/update` is not present in the reconciled Promos endpoint set.
- Explicitly rejected substituting `activate` for update because its documented semantics are adding products to a promotion.
- Added adapter contract tests for the reconciled read schemas and the mutation safety block.


## 2026-10-01 — Mutation Safety Hardening

- Connected `MutationService` batching to `Settings.batch_size`; removed the duplicate service-level batch constant.
- Removed the misleading `read_participants_v2` name; read-after-write uses the verified `/v1/actions/products` contract.
- Stopped hardcoding mutation transport status; the result now carries adapter-reported status.
- Distinguished `UNKNOWN_RESULT` from explicit API/unsupported-operation failures; no blind retry is introduced.
- Network request failures are classified as `UNKNOWN_RESULT` because mutation outcome cannot be assumed from a missing response.
- Updated API documentation to keep the unverified mutation contract explicitly blocked.

## 2026-10-01 — Final Mutation API Contract Reconciliation

- Confirmed `POST /v1/actions/products/update` from the reviewed Ozon Seller API OpenAPI contract.
- Implemented the verified update request with `action_price.amount` + `action_price.currency`.
- Implemented `active_product_ids`, `deactivated_product_ids`, `rejected`, and `warnings` response handling.
- Switched candidate and participant reads to `/v2/actions/candidates` and `/v2/actions/products` with cursor `last_id`.
- Preserved optional `stock` semantics: omitted is different from explicit zero.
- Removed the previous hard block that incorrectly treated the update endpoint as unverified.
- Updated Fresh Check so it does not invent membership/availability fields absent from the current v2 participant schema.
- Added adapter contract tests for v2 reads, update payload, partial results, 1000-item boundary, and current participant field shape.
- Live authenticated mutation remains a separate acceptance gate; no production mutation was executed by this change.

## 2026-10-01 — Candidate/participant table UX

- Candidate and participant data are now presented in separate dialog windows instead of one combined table.
- Both table dialogs are closed by default and opened explicitly by the user.
- Mutation selection remains restricted to products returned by the participant endpoint.
- Ozon money objects such as `{'amount': '2700', 'currency': ''}` are rendered as `2700` in the UI.
- Numeric values are normalized to remove unnecessary `.0` suffixes.
- Nested `website_prices` values are flattened into readable amount entries instead of raw dictionary syntax.
- Added per-column descriptions inside each table dialog.
- Added unit coverage for display normalization and candidate/participant table formatting.

## 2026-10-01 — Phase 4D partial OzonAPI integration

- Added an isolated `OzonSDKPromotionsReader` boundary around OzonAPI `SellerAPI.actions()`.
- Delegated only the read-only `/v1/actions` operation to OzonAPI 0.89.0 when `OZON_USE_SDK=1`.
- Kept candidate and participant reads on the direct adapter because the audited SDK `ActionProduct` model does not preserve the richer Elastic Boosting product fields used by the application.
- Kept mutation on the existing adapter; OzonAPI does not expose `/v1/actions/products/update` in its audited API surface.
- Added SDK integration tests with a mocked OzonAPI module; no real Ozon mutation was executed.

## Product names via OzonAPI

- Added read-only OzonAPI `product_info_list()` integration for `/v3/product/info/list`.
- Candidate and participant Product IDs are enriched with product-card names before rendering.
- Missing names are shown as `UNKNOWN`; name lookup failure does not block read-only product tables.
- No mutation path depends on the product-name lookup.
- No undocumented batch-size limit is hardcoded for product-info lookup; current API limit remains UNKNOWN until separately reconciled against the current official Ozon contract.

## Performance Fix — Product Names / Streamlit Read Cache

- Added per-session read cache for promotions, candidates and participants.
- Added 60-second TTL for cached read data.
- Added explicit `🔄 Обновить данные` action for forced refresh.
- Product names are resolved only for Product IDs not already cached in the current session.
- Added 900-product regression coverage without real Ozon mutation.
- Kept credentials out of the cache; `st.cache_data` was deliberately not used for credential-bearing Ozon reads.

## Phase 4D — performance regression hardening

- restored mandatory `.env.example` with no real credentials;
- added a 900-Product-ID read-cache regression test proving no duplicate reads
  on normal Streamlit reruns and delta-only name resolution for newly seen IDs;
- verified `pytest` and Python compile checks after the change.

### QA hardening — 2026-10-01
- Added 863-product candidate pagination regression coverage.
- Added 863-product participant pagination regression coverage.
- Fixed Product ID fallback when candidate `id` is null and `product_id` is present.
- Verified 59 pytest tests pass; no real mutation executed.

- Added separate candidate/participant selection workflows in Streamlit.
- Added ADD-to-promotion flow using the reconciled legacy `activate` contract, with mandatory Fresh Check, Snapshot, confirmation and read-after-write verification.
- Added participant price update flow with deterministic percentage/ruble/exact-price calculation, rounding and optional Safety Floor.
- Added participant REMOVE flow using `/v2/actions/products/deactivate` with confirmation and verification.
- Added operation type persistence (`ADD_PRODUCTS`, `UPDATE_PRICE`, `REMOVE_PRODUCTS`) to SQLite history.
- Replaced the product-name count caption with the current `HH:MM` refresh time.

## Elastic Boosting UI recalculation update

- Candidate table reduced to the requested columns: SKU, Название, Цена, Max action price, Alert max action price failed, Alert max action price, Price min elastic, Price max elastic.
- Candidate Elastic Boosting calculation now uses the Ozon candidate `price` field as the calculation base; `action_price` is not used as the candidate base price.
- `max_action_price` is informational only and is not used as a calculation floor.
- Example covered by tests: 2700 with -22% gives 2106, but with max_action_price 2314 the final price is 2314.
- Visible operation tables now use SKU instead of internal Product ID; internal Product ID remains the mutation identifier.

## UI — Account and navigation hardening

- Renamed the application title to `Менеджер Ozon`.
- Removed the `Elastic Boosting — расчёт от цены товара` subtitle from the main screen.
- Replaced the persistent Client ID/API Key sidebar fields with an `Аккаунт` dialog.
- Credentials remain in Streamlit session state only; API Key is never rendered in plaintext outside the password input.
- Renamed the Ozon connection check to `Проверить подключение к Ozon`.
- Sidebar order is now: `Аккаунт` → `Mock mode` → `Обновить данные` → `История`.
- Added `← Назад к меню` navigation to Actions, Stocks, and History.
- Existing Actions/History services and mutation workflows were not changed.
## UI table hardening — 2026-10-02

- Removed the redundant promotion header/action description from the Actions view; products open immediately.
- Removed the column-help expander and dialog close-hint text from product tables.
- Replaced product/read-only Streamlit tables with a shared interactive table component.
- Added reliable numeric/text sorting by left-clicking a column header.
- Added per-column context filters via right-click on the column header.
- Added Shift+left-click range selection for product tables.
- Added hundredths precision to the discount slider (1.00–18.00%) with 5% and 10% visual scale marks.
- Kept the per-product double-click discount editing flow.
- Preserved existing mutation, preview, fresh-check, snapshot, reconciliation and rollback services.

### UI visual refresh — Ozon Seller reference
- Updated Streamlit shell styling to match the supplied Ozon Seller HTML references: Onest typography, cool-gray workspace, white surfaces, compact navigation, Ozon blue primary actions, restrained borders and radii.
- Restyled the shared product table without changing its sorting, filtering, selection, Shift-range selection, copy, or mutation behavior.
- No Ozon API, business logic, or data-contract changes.

## Browser E2E baseline

- Added Streamlit AppTest smoke layer.
- Added Playwright + Chromium real-browser acceptance layer.
- Added baseline table interaction E2E coverage for sorting, context filtering, Shift-range selection, scroll preservation, package discount editing and SKU deletion.
- Mock dataset expanded to 20 products so the 12-row table viewport can be exercised with real scrolling.

## 2026-10-02 — Auto-Add threshold deletion mutation
- Added `AutoAddDeleteService` for threshold-based removal from Ozon scheduled Auto-Add.
- Mutation contract wired to `POST /v1/actions/auto-add/products/delete` with `action_id`, Ozon-provided `auto_add_date`, and `product_ids`.
- Added Preview, Fresh Check, Snapshot-before-mutation, explicit confirmation and read-after-write reconciliation.
- Mutation is never retried after an ambiguous transport result; reconciliation is read-only.
- The UI threshold remains strict: `Скидка > N%` is deleted; `Скидка == N%` is retained.
- Rollback from Auto-Add is not enabled yet; restoration requires a separately audited Auto-Add update contract.

## Auto-Add rollback hardening

- Added `AUTO_ADD_ROLLBACK` service with Preview, Fresh Check, dedicated pre-mutation snapshot, confirmation, final Fresh Check and read-after-write reconciliation.
- Added `POST /v2/actions/auto-add/products/update` adapter contract from the current Ozon-compatible SDK model.
- Added explicit rollback verification states: `CONFIRMED_RESTORED`, `UNKNOWN_NOT_PRESENT`, `RESTORED_PRICE_MISMATCH`, `UNKNOWN`.
- Added Auto-Add snapshot date/presence metadata and a dedicated absent-state snapshot table.
- Real-account rollback mutation remains `LIVE_VERIFICATION_UNKNOWN` until controlled acceptance captures the actual Ozon response.
## 2026-10-03 — Windows QA: UTF-8 source contracts and browser discovery

- UI source-contract tests now read UTF-8 explicitly instead of relying on the Windows locale (`cp1251`).
- Browser E2E fixtures now detect Playwright-managed Chromium before falling back to a system Chromium/Chrome executable.
- The interactive table component retains the required `Shift+ЛКМ по чекбоксу — диапазон` contract text.
- No production business logic or Ozon API contract was changed.
## 2026-10-03 — Playwright browser fixture hardening

- Removed the nested `sync_playwright()` call from the browser fixture path.
- Playwright-managed Chromium is now used through the active Playwright context when no system Chromium/Chrome executable is present.
- Component browser contract tests use the same fallback instead of incorrectly skipping when only managed Chromium is installed.
- No production business logic or Ozon API behavior changed.


## 2026-10-03 — Elastic ADD boundary / package editor fix

- Fixed two-decimal discount boundary handling for candidate ADD: displayed boundary percentages now resolve to Ozon's exact `price_min_elastic` / `price_max_elastic` monetary thresholds.
- Fixed inline discount editing in the accumulated ADD package editor so both display-layer discount field names are editable and persist the recalculated absolute price.
- Fixed SKU-row removal event handling and replaced the emoji delete glyph with an accessible SVG icon, preventing the icon from becoming part of copied SKU text.


## 2026-10-03 — ADD package editor identity fix
- Price dialog rows now use Product ID as the component row identity; SKU remains display-only.
- Inline discount and row removal therefore target the actual Product ID.
- Elastic boundary calculation is currency-normalized and accepts the displayed two-decimal boundary as an alias of Ozon's exact threshold.

## 2026-10-03 — Participant price update / table interaction hardening

- Participant price editing now uses the same per-product Ozon `price_min_elastic` / `price_max_elastic` thresholds as candidate ADD; the former application-side 1%–18% rule is no longer used for participant updates.
- Participant UPDATE_PRICE service validates the requested absolute price against the current Ozon Elastic Boosting range after Fresh Check and before snapshot/mutation.
- Participant price-edit state survives Streamlit reruns and the update confirmation is stored in `update_price_plans` for the verification/send stage.
- The shared table selection header now selects/deselects all visible rows.
- Shift+RMB on a row selects the visible range from the current selection anchor; Shift+LMB remains supported.
- ADD mutation now exposes a visible operation status screen and a persistent post-operation confirmation/result view instead of immediately dropping the operation table.

## 2026-10-03 — Stocks section

- Replaced the Stocks placeholder with a real FBS/rFBS stock-management workflow.
- Added Ozon stock-by-warehouse read and stock mutation adapter methods.
- Added stock search, warehouse/availability filters, sorting, pagination and inline stock editing.
- Added mass stock changes with explicit confirmation.
- Added Fresh Check, SQLite snapshot, per-item mutation results and read-after-write reconciliation.
- Added dedicated stock operation history, isolated from promotion history.
- Added stock API audit documentation and regression/contract tests.

## 2026-10-03 — Stocks 02A Mutation QA hardening

- Added fail-closed handling for read-after-write transport failures after a successful mutation response.
- If the verification read fails, accepted mutation items are persisted as `UNKNOWN_RESULT` and the operation is persisted as `UNKNOWN_RESULT`; the mutation is never retried automatically.
- Added regression coverage for duplicate product–warehouse pairs and negative stock values before snapshot creation.
- Added a 900-record mutation batching contract test (9 × 100) without real Ozon writes.
- Added a second-batch HTTP 429 test proving completed batches are not blindly retried.
- Full pytest regression and Python compile check pass.

Controlled live Stocks verification remains limited to the explicitly executed single-item and three-item scenarios; negative/error scenarios are mock-only.

## 2026-10-03 — Stocks 02B combined mutation hardening

- Blocked repeated execution of terminal Stocks operations.
- Added persisted operation/snapshot identity and snapshot-existence checks before mutation.
- Added explicit `UNKNOWN_RESULT` presentation in Stocks UI.
- Added snapshot-backed rollback preparation directly from Stocks History.
- Added realistic 100 + 1 second-batch 429 QA scenario with no blind retry of the completed first batch.
- Strengthened 900-record service stress to exercise nine 100-item batches without real Ozon mutation.
- Added security/runtime hygiene audit coverage and updated release documentation.

## FIX4 — History rollback / dialog / input-state hardening — 2026-10-03

- Stocks rollback sources in History are now restricted to operations with `SUCCESS` status and an existing snapshot. Other historical operations remain visible for audit but cannot be selected as rollback sources.
- Fixed `StreamlitInvalidLayoutContextError` for Auto-Add Rollback: a pending Auto-Add rollback dialog suppresses the underlying History dialog, guaranteeing one dialog per Streamlit script run.
- Table filter input no longer restores the previously typed filter value when reopened; browser autocomplete/history is disabled for the shared table filter input.
- Auto-Add discount input has browser autocomplete disabled.
- Account dialog is automatically opened once at the beginning of a new Streamlit session and is not repeatedly reopened on ordinary reruns.
- Added UI contract/regression tests for all four changes.

### 2026-10-03 — FIX: История → Акции

- Исправлено падение `IndexError: No item with that key` в окне «История → Акции».
- Причина: `product_count`, `success_count` и `failed_count` не являются физическими колонками `operations`; они вычисляются из `operation_items`.
- `SQLiteRepository.list_operations()` теперь возвращает эти показатели как вычисляемые поля через агрегированный SQL-запрос.
- Совместимость со существующими SQLite-базами сохранена; миграция данных не требуется.
- Добавлен регрессионный тест на количество товаров, успешных и неуспешных элементов операции.

## REMOVE forensic verification — 2026-10-04

- Live-verified Elastic Boosting REMOVE for action `1977747`, product `6238154899` / SKU `5710841509`.
- Confirmed that `/v1/actions/products/update` with `action_price=1510` returned the product in `active_product_ids` and did not remove it.
- Confirmed that `/v1/actions/products/deactivate` returned the product in `result.product_ids` and the participant disappeared on read-after-write.
- Hardened REMOVE service reconciliation to require explicit Ozon acknowledgement (`deactivated_product_ids`), reject explicit per-product rejections, and still require read-after-write absence.
- Recorded the 2026-10-13 deprecation/shutdown date as a compatibility risk; no unverified replacement transport was introduced.

## 2026-10-04 — Price validation / candidate discount / rollback hardening

- Fixed Participant UPDATE global percentage application: UI now supplies canonical `price_min_elastic` / `price_max_elastic` fields to the validation service.
- Added `Скидка` to the Candidates table as an Ozon-derived per-product discount interval (`min% → max%`) calculated from `price`, `price_min_elastic`, and `price_max_elastic`.
- Reworked safe promotion rollback membership semantics:
  - ADD rollback → REMOVE;
  - REMOVE rollback → ADD using the positive `action_price` from the source snapshot;
  - UPDATE rollback → existing participant `action_price` restoration.
- Added regression tests for global percentage validation, candidate discount display, and both inverse membership rollback directions.
- Full automated verification: 250 passed, 1 skipped; `compileall` PASS.

## 2026-10-05 — Auto-Add all actions UI V1

- `Автодобавление Ozon` теперь открывает hub всех акций с `auto_add_dates`.
- Убрано количество с основной кнопки, текст центрирован.
- Акции расположены в две колонки; таблица загружается только после выбора акции.
- Существующий Auto-Add mutation workflow не изменён.
- Подробности: `docs/AUTO_ADD_ALL_ACTIONS_UI_V1.md`.
