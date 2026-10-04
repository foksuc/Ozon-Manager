> **Current release context — 04.10.2026:** This file is a historical phase report. Its dated findings are preserved for traceability. For the current release status, use `docs/RELEASE_AUDIT.md`, `docs/API_RECONCILIATION.md` and `README.md`.

# Phase 4D — New Version Audit + Partial OzonAPI Integration

Date: 2026-10-01

## Baseline

- Input: `Ozon-Manager-phase4d-table-dialogs.zip`
- Baseline automated tests: 47 passed.
- Architecture already separated UI, services, domain, adapter, repository and mock adapter.
- Candidate/participant tables were already split into separate dialogs and the participant table already exposed `Название`.

## Audit findings

### Confirmed in project

- Preview/Fresh Check/Snapshot/Confirmation/Mutation/Read-after-write workflow exists.
- Mutation is restricted to participant products.
- Candidate and participant datasets are kept separate.
- Partial mutation results are classified.
- Unknown mutation outcomes are fail-closed; no blind retry is performed.
- SQLite history/snapshot infrastructure exists.
- Mock adapter and regression tests exist.
- Credentials are supplied through UI/environment and are not embedded in project files.

### Important contract risks

1. The current project documents `/v1/actions/products/update` as reconciled, but this operation is not present in the audited OzonAPI API surface. It remains a separate contract gate and was not moved into the SDK.
2. The current OzonAPI repository exposes `/v1/actions`, `/v1/actions/candidates`, `/v1/actions/products`, activate/deactivate, and price import methods, but not the project's update endpoint.
3. OzonAPI's `ActionProduct` model is narrower than the application's Elastic Boosting participant model, so replacing direct product reads with SDK deserialization would lose fields.
4. OzonAPI's `manage_elastic_boosting_through_price` field was not adopted as an Elastic Boosting mutation mechanism.
5. A live authenticated mutation was not executed.

## Changes made

### Added

- `app/adapters/ozon_sdk.py`
  - isolated OzonAPI integration boundary;
  - SDK-backed `/v1/actions` read;
  - response normalization into the project's `Promotion` model;
  - SDK errors mapped without exposing credentials.
- `tests/test_sdk_partial_integration.py`
  - mocked SDK integration test.
- `docs/OZONAPI_PARTIAL_INTEGRATION.md`
  - integration boundary and safety rationale.
- this report.

### Modified

- `app/adapters/ozon.py`
  - optional SDK delegation for `list_promotions()`;
  - candidates, participants and mutation remain on direct HTTP adapter;
  - `OZON_USE_SDK` runtime switch added.
- `requirements.txt`
  - added `ozonapi-async==0.89.0`.
- `tests/test_adapter_contract.py`
  - transport tests explicitly disable SDK delegation.
- `docs/CHANGELOG.md`
  - recorded the partial SDK integration.

## New functionality

- SDK-backed promotion loading through OzonAPI.
- Runtime ability to switch SDK promotion reads on/off with `OZON_USE_SDK`.
- Explicitly isolated SDK boundary so future SDK expansion can be audited per operation.
- Regression coverage proving SDK integration does not alter candidate/participant/mutation transport contracts.

## Verification

- `pytest -q`: 48 passed.
- `python -m compileall -q app tests`: PASS.
- No real Ozon mutation executed.
- SDK integration was tested with a mocked SDK module.

## Remaining gates

- Independently capture current official Ozon OpenAPI evidence for `/v1/actions/products/update` before treating mutation as externally verified.
- Capture a controlled authenticated read response for the target promotion(s).
- If mutation contract is independently confirmed, perform a separate controlled live acceptance test; otherwise keep mutation fail-closed.
- Do not replace candidate/participant reads with OzonAPI until its schemas preserve every field required by the UI and Fresh Check.

## QA verification — 2026-10-01

- Real user dataset size reported: 863 products.
- Candidate pagination regression: 863 records reconstructed across 9 cursor pages with no loss.
- Participant pagination regression: 863 records reconstructed across 9 cursor pages with no loss.
- Product ID fallback verified when `id` is `None` and `product_id` is populated.
- Existing 900-product name-cache regression remains passing.
- No Ozon mutation executed during this QA pass.
- Final automated test count after QA hardening: 59 passed.
