# Test Plan

## Current release verification — 2026-10-04

- `pytest -q`: **256 passed, 1 skipped**.
- `python -m compileall -q app tests`: **PASS**.
- The current suite includes domain, service, adapter contract, mutation safety, Stocks, UI contract and security checks.
- No live mutation is performed by the automated suite unless explicitly represented by a controlled project verification record.

## Unit

- state transitions;
- validation;
- Preview;
- Fresh Check;
- Snapshot;
- verification;
- rollback target selection.

## Integration

- SQLite persistence;
- mock adapter;
- operation history;
- partial outcomes.

## Contract

- verified read endpoint method/path/payload;
- participant read path;
- post-write read uses the same verified participant endpoint;
- mutation remains blocked until its contract is verified;
- malformed response/error classification.

## Bulk

- 1 SKU;
- 10 SKU;
- 100 SKU;
- 1000 SKU preview/batch planning without real Ozon mutation;
- 900 SKU mock mutation stress run without real Ozon mutation.

## Safety cases

- mutation without Preview;
- mutation without Fresh Check;
- mutation without Snapshot;
- mutation without Confirmation;
- stale action_price;
- stale current_boost;
- timeout after unknown mutation;
- partial rejection;
- read-after-write mismatch;
- Target Boost request;
- base price field leakage into mutation payload.

## Mutation Safety QA — 2026-10-01

Automated mock-adapter verification completed against the current build.

- Preview gate: PASS
- Fresh Check gate: PASS
- Snapshot-before-mutation gate: PASS
- Confirmation gate: PASS
- Pre-mutation Fresh Check: PASS
- Stale action_price blocked before mutation: PASS
- Stale current_boost blocked before mutation: PASS
- Inactive promotion blocked before mutation: PASS
- Partial rejection + per-SKU persistence: PASS
- Read-after-write mismatch: PASS
- Unknown mutation result: FAIL-CLOSED / PASS
- Unknown result after state change: blind retry blocked / PASS
- Duplicate operation fingerprint: blocked / PASS
- Rollback as a new snapshot-backed mutation: PASS
- Rollback stale-state protection: PASS
- Snapshot linkage persisted before confirmation: PASS

Current automated suite for the current build: **256 passed, 1 skipped**. The single skip is the environment-dependent Streamlit smoke test when Streamlit is unavailable in the test environment.

No authenticated live Ozon mutation was executed during this QA. A controlled live probe remains a separate release gate.

## UI application-level verification

The project uses `streamlit.testing.v1.AppTest` for application-level startup and high-level UI contract checks.

A real-browser Playwright/Chromium E2E layer was removed from the project and is **not a release gate**. The previous browser harness depended on Streamlit component iframe/browser lifecycle details and produced environment/harness failures that were not reliable evidence of production UI defects.

UI behavior that can be verified deterministically at the application/component contract level remains covered by the existing Python tests.

## Candidate ADD Elastic Boosting bounds

Required regression cases:

- `Цена=2700`, `price_min_elastic=2314`, `price_max_elastic=1913`;
- calculated minimum discount rounds to `14.30%`;
- calculated maximum discount rounds to `29.15%`;
- a price above `2314` is rejected before mutation;
- a price below `1913` is rejected before mutation;
- a price at the activation boundary is accepted;
- rounded display input `29.15%` is validated by resulting price, not by the
  rounded percentage itself;
- missing/inconsistent Elastic Boosting thresholds block ADD fail-closed;
- Fresh Check still revalidates the threshold fields before mutation.


## Participant global percentage regression

- selected global percentage below one product's minimum → reject whole package;
- selected global percentage equal to each product's minimum → accepted;
- selected global percentage inside all product ranges → one absolute price calculated per product;
- selected global percentage above one product's maximum → reject whole package;
- no package mutation when validation fails;
- no fixed `1%–18%` UPDATE constraint is asserted.

## Loading modal regression

Contract coverage verifies the centered `_loading_overlay()` is wired into connection checks, Ozon reads, card enrichment, reconciliation, rollback, REMOVE, ADD and Participant UPDATE paths. The UI contract does not rely on browser E2E.

## Stocks Mutation QA — 2026-10-03 / 02A hardening

### Controlled live verification

The current build has been manually verified against the live Ozon account for:

- single item `3 → 4`;
- single item `4 → 3`;
- single item `3 → 7`;
- single item `7 → 3`;
- three-item mutation `3 → 4`, `1 → 3`, `3 → 4`;
- reverse three-item mutation `4 → 3`, `3 → 1`, `4 → 3`.

All reported scenarios completed successfully and the tested values were restored to their original state.

### Mock / contract QA

- read-after-write transport failure → `UNKNOWN_RESULT`, no mutation retry: PASS;
- duplicate product–warehouse pair → blocked before snapshot: PASS;
- negative stock → blocked before snapshot: PASS;
- 900 mutation records → 9 × 100 transport batches: PASS;
- second-batch 429 → no blind retry of completed batch: PASS;
- existing timeout / partial response / rollback / Fresh Check scenarios: PASS;
- full project pytest regression: PASS;
- `python -m compileall -q app tests`: PASS.

### Remaining release gates

- controlled real multi-batch mutation above the minimum tested set is intentionally not required for this QA patch;
- live 429/timeout/partial-failure injection is not performed against production Ozon;
- any Ozon-specific retry/window semantics not established by authoritative current documentation remain `UNKNOWN`.

## Stocks Mutation QA 02B — combined patch

### Safety / persistence

- terminal operation cannot be executed twice: PASS;
- missing persisted snapshot blocks mutation: PASS;
- operation/snapshot identity mismatch blocks mutation: PASS;
- rollback preparation from History snapshot: source-contract PASS;
- rollback remains a new snapshot-backed mutation: PASS.

### Partial / rate-limit behavior

- 101 records modeled as 100 + 1: PASS;
- first batch accepted, second batch returns HTTP 429: PASS;
- first batch is not resent: PASS;
- second batch is not blindly retried: PASS;
- accepted first-batch items are persisted as SUCCESS; unresolved second-batch item is UNKNOWN_RESULT: PASS.

### Stress

- 900 stock changes through the service with a 100-item batching adapter: PASS;
- nine 100-item batches completed without real Ozon mutation: PASS.

### UI / History

- separate confirmation dialog remains the mutation gate: PASS;
- History exposes snapshot-backed `Подготовить rollback`: PASS;
- UNKNOWN_RESULT is displayed separately from generic ERROR: PASS;
- rollback preparation uses the shared loading overlay: PASS.

### Security / hygiene

- `.env` absent from release tree: PASS;
- `.streamlit/secrets.toml` absent from release tree: PASS;
- runtime `logs/` absent from release tree: PASS;
- no real credential values found by source scan: PASS.
