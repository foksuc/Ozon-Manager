> **Current release context — 04.10.2026:** This file is a historical phase report. Its dated findings are preserved for traceability. For the current release status, use `docs/RELEASE_AUDIT.md`, `docs/API_RECONCILIATION.md` and `README.md`.

# PHASE D.3 — Mutation Contract Reconciliation

**Date:** 2026-10-01

## Status

**PASS for adapter contract migration; production release remains blocked by other audit items.**

## What was checked

1. Current participant/candidate classification for Product ID `1508648261`.
2. Current published activate/deactivate request and response schemas.
3. Live `activate` behavior on an already participating Elastic Boosting product.
4. Read-after-write after the live mutation.
5. Restoration of the original action price.
6. Existing adapter and workflow contract against the verified behavior.

## Live classification

For action `1977747`:

```text
Product ID 1508648261
SKU         1950676321
participant = true
candidate   = false
add_mode    = MANUAL
action_price = 1005
```

The same product was changed live from `1005` to `1004` through `/v1/actions/products/activate`, then restored to `1005`. Both mutations returned HTTP 200 with the product in `result.product_ids` and no rejection. Read-after-write confirmed both values.

## Contract decision

| Operation | Decision |
|---|---|
| Candidate read | `/v2/actions/candidates` |
| Participant read | `/v2/actions/products` |
| ADD | `/v1/actions/products/activate` |
| UPDATE action_price | `/v1/actions/products/activate` for a participant, after Fresh Check |
| REMOVE | `/v1/actions/products/deactivate` |
| `/v1/actions/products/update` | **DO NOT USE / UNVERIFIED** |

## Partial failure rule

The current published activate/deactivate contract returns accepted IDs and a `rejected` collection. Therefore the application must:

- preserve every rejected product and reason;
- never classify HTTP 200 as all-success;
- verify accepted products by read-after-write;
- classify mixed accepted/rejected batches as `PARTIAL`;
- never blindly retry a mutation whose transport outcome is unknown.

## Code changes made

- `app/adapters/ozon.py`
  - removed calls to `/v1/actions/products/update`;
  - `update_products()` now uses the live-verified activate contract;
  - activate/deactivate parse the `result` envelope;
  - partial rejections are preserved in `MutationResult`;
  - deactivate uses the current v1 documented contract;
  - removed the unverified 1000-product API-limit hard-code.
- `app/services/membership.py`
  - ADD sends `action_price` during activation;
  - removed the unnecessary second price mutation for ADD;
  - handles per-product rejection and verifies resulting action price.
- `app/adapters/mock.py`
  - mock activation now mutates action price and returns partial results.
- tests
  - adapter contract tests updated to the live-verified endpoint and response shape.

## Test result

```text
pytest: PASS
compileall: PASS
```

The full project test suite passes after the contract migration.

## Still UNKNOWN

- exact current maximum batch size for activate/deactivate;
- exact `stock` semantics and whether the field is mandatory in every ADD scenario;
- mutation behavior under 429/timeout after server-side acceptance;
- live REMOVE partial-failure behavior.

These remain separate acceptance items and are not inferred from the current evidence.


## Post-write reconciliation incident — 2026-10-01

The supplied production SQLite history for action `1977747` contains one ADD
operation with three products:

- `5627606379`: requested `820.00`, read-back `820` — already confirmed.
- `1653268649`: requested `885.60`, read-back `886`.
- `4871823775`: requested `885.60`, read-back `886`.

For the two latter products the source price was `1080`, so the read-back
discount is `(1080 - 886) / 1080 × 100 = 17.962962...%`. The mutation was not
repeated; the operation remained in `VERIFICATION_FAILED` only because the
old reconciliation compared Decimal values literally.

Decision: whole-RUB `ROUND_HALF_UP` read-back is an ordinary confirmed
`SUCCESS` for reconciliation. No separate `normalized` status is added.
