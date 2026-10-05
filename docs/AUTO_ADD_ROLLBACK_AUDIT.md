> **Current release context — 04.10.2026:** Historical/date-specific findings in this document are preserved. Current release verification is **256 passed, 1 skipped** with `compileall` PASS. Known Promotions API shutdown risk is documented in `docs/API_RECONCILIATION.md` and `docs/RELEASE_AUDIT.md`.

# Auto-Add Rollback — API Audit & Acceptance Status

Date: 2026-10-02

## 1. Source hierarchy

1. Official Ozon Seller API documentation / Swagger: endpoint catalogue evidence is available through the project's API reconciliation source.
2. Current Ozon-compatible Go SDK source: `promotions_auto_add_v2.go`.
3. Project adapter and tests.

## 2. Contract finding

The current SDK exposes:

`POST /v2/actions/auto-add/products/update`

Request:
- `action_id`
- `auto_add_date`
- `products[]`
- `products[].id`
- `products[].action_price` (`amount`, `currency`)
- optional `products[].stock`

Response model preserves:
- `product_ids`
- `deactivated_ids`
- `rejected`
- `warnings`
- `below_min_price`
- `extremely_low_price`
- `failed_price`

The same SDK describes the operation as adding or updating products in scheduled Auto-Add.

## 3. Current verification status

The project has a controlled Auto-Add rollback verification on record. The rollback flow completed successfully and restored all six test SKUs with status `CONFIRMED_RESTORED`.

**Auto-Add rollback: CONFIRMED / PASS.**

This status is based on the project verification result, not on SDK model definitions alone.

## 4. Safety contract implemented

Rollback flow:

`source snapshot → Preview → read-only Fresh Check → dedicated pre-mutation absent-state snapshot → user confirmation → final Fresh Check → UPDATE mutation → read-after-write reconciliation`

Blind mutation retry is prohibited.

Reconciliation states:
- `CONFIRMED_RESTORED`
- `RESTORED_PRICE_MISMATCH`
- `UNKNOWN_NOT_PRESENT`
- `UNKNOWN`

## 5. Snapshot changes

`promotion_snapshots` now records:
- `auto_add_date`
- `present`

A dedicated `auto_add_snapshots` table records an exact absent pre-rollback state.

Existing snapshots are migrated without data loss. Existing historical Auto-Add DELETE snapshots whose date is NULL are not guessed or repaired automatically.

## 6. Tests

Added coverage for:
- update adapter wire contract;
- successful Auto-Add rollback;
- rollback Fresh Check when the product reappeared;
- price mismatch after restore;
- snapshot presence state;
- full regression suite.

Current automated result: the relevant Auto-Add rollback tests pass. Browser E2E is not part of the project test stack.

## 7. Release status

The Auto-Add rollback workflow is **confirmed**. It remains subject to the same global release gates as every other mutation: final regression, security audit, 900-SKU mock stress, and clean-install verification.
