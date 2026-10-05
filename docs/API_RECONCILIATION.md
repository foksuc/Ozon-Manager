# Current contract addendum — 2026-10-04

## Release status

The project source and tests were rechecked for the 2026-10-04 local release. The current adapter still uses the live-verified legacy promotion mutation transports described below. The bundled Ozon API forensic snapshot records their planned shutdown on **2026-10-13**. This is a known compatibility risk for the next release, not a reason to invent an unverified replacement in the current build.

- `POST /v1/actions/products/activate`: current ADD / participant `action_price` UPDATE transport used by the adapter; live-verified earlier.
- `POST /v1/actions/products/deactivate`: current REMOVE transport used by the adapter; live-verified for Elastic action `1977747` on 2026-10-04.
- Both legacy mutation endpoints are scheduled for shutdown on 2026-10-13 according to the bundled API reference.
- `/v1/actions/products/update` is not silently substituted for the above operations.
- No claim is made that the post-shutdown replacement is already implemented or verified.

## Current QA

- `pytest -q`: **256 passed, 1 skipped**.
- `python -m compileall -q app tests`: **PASS**.

Historical evidence and phase-specific conclusions remain below for traceability.

---

# Current contract addendum — 2026-10-03

The current project build supersedes the historical D.3 wording below where it conflicts with later controlled verification.

- Existing-participant Participant UPDATE is routed by adapter `update_products()` through the live-verified `POST /v1/actions/products/activate` transport. `/v1/actions/products/update` remains unused and unverified.
- The controlled Auto-Add rollback workflow has been executed successfully in the project and restored six test SKUs to `CONFIRMED_RESTORED`.
- The UI's Participant UPDATE price range is derived from the current participant `price_min_elastic` / `price_max_elastic`; there is no fixed 1%–18% UPDATE business rule.
- A global percentage can be applied to a Participant UPDATE package only after per-product range validation.

Historical evidence and phase-specific conclusions remain below for traceability.


### ADD post-write verification clarification — 2026-10-01

For `ADD_PRODUCTS`, the mutation response and the subsequent participant read have different evidentiary roles:

- `rejected` from Ozon is an explicit per-product rejection and is stored as `REJECTED` with its reason.
- A participant read with `action_price == requested` is `SUCCESS`.
- A participant read with `action_price != requested` is a real `PRICE_MISMATCH`.
- If the participant is not visible in the post-write read, the outcome is `UNKNOWN_RESULT`; the application does not infer rejection or mismatch from absence.
- `UNKNOWN_RESULT` is fail-closed: no automatic repeat mutation is allowed. History provides a read-only reconciliation action.

This distinction is required because a read-after-write miss does not by itself prove that the mutation failed.

# Ozon API Contract Reconciliation — 2026-10-01

## Scope

Final forensic reconciliation of the Promotions / Elastic Boosting adapter against the current Ozon Seller API contract reviewed on 2026-09-28 and applied to the project on 2026-10-01.

## Evidence hierarchy

1. Ozon Seller API documentation/OpenAPI.
2. Current published Ozon Seller API documentation checked on 2026-10-01.
3. Live authenticated read evidence from action 1977747.
4. Controlled live mutation evidence for an existing Elastic Boosting participant.
5. Adapter contract tests.

The reviewed OpenAPI source was:

`https://docs.ozon.ru/api/seller/swagger.json?1790601089484`

The reviewed operation pages include `Promos`, `ActionsCandidates`, `ActionsProducts`, `ActionsProductsUpdate`, and `ActionsProductsDeactivate`. The 2026-10-04 controlled REMOVE mutation supersedes the previous "not yet executed" status for `/v1/actions/products/deactivate`.

## Final contract matrix

| Operation | Method | Path | Contract status | Evidence / decision |
|---|---|---|---|---|
| Promotions | GET | `/v1/actions` | CONFIRMED | Live HTTP 200; action 1977747 returned. |
| Candidates | POST | `/v2/actions/candidates` | CONFIRMED | Live HTTP 200; top-level `products`, `total`, `last_id`. |
| Participants | POST | `/v2/actions/products` | CONFIRMED | Live HTTP 200; target participant returned with `action_price`, boost fields. |
| ADD / action-price mutation | POST | `/v1/actions/products/activate` | **LIVE VERIFIED** | Existing participant changed `action_price` 1005 → 1004 and read-after-write confirmed it; restore 1004 → 1005 also confirmed. |
| REMOVE | POST | `/v1/actions/products/deactivate` | **LIVE VERIFIED (2026-10-04)** | Controlled Elastic Boosting action 1977747 mutation removed product 6238154899; response returned it in `result.product_ids` and read-after-write confirmed absence. Endpoint is deprecated and scheduled for shutdown 2026-10-13. |
| `/v1/actions/products/update` | POST | `/v1/actions/products/update` | **NOT CONFIRMED / DO NOT USE** | Not present in current published Promotions catalog checked for this phase; adapter no longer calls it. |
| Auto-Add DELETE | POST | `/v1/actions/auto-add/products/delete` | **LIVE VERIFIED** | Controlled account mutation already completed; DB reconciliation confirms `CONFIRMED_REMOVED` for all tested products. |
| Auto-Add rollback/update | POST | `/v2/actions/auto-add/products/update` | **IMPLEMENTED / CONTROLLED VERIFIED** | Project rollback verification restored six test SKUs to `CONFIRMED_RESTORED`; transport remains isolated behind the adapter. |

## Live UPDATE finding

For action `1977747` (Elastic Boosting), Product ID `1508648261` was already a participant (`add_mode=MANUAL`, `action_price=1005`). A controlled call to:

```text
POST /v1/actions/products/activate
```

with the same participant and `action_price=1004` returned HTTP 200 with `product_ids=[1508648261]` and `rejected=[]`. A subsequent participant read returned `action_price=1004`. A second controlled call restored `1005`, and read-after-write returned `1005`. `current_boost` moved 20.2 → 20.4 → 20.2 in the same sequence.

This establishes a **live-verified mechanism for changing `action_price` of an existing Elastic Boosting participant**. It does not establish that `activate` is a generic replacement for every possible promotion workflow; membership classification remains a service-layer responsibility.

## Mutation response contract

The published activate/deactivate documentation exposes per-product results under `result`: `product_ids` for accepted products and `rejected` entries for products not accepted. Therefore HTTP 200 is not sufficient for business-level success; the adapter preserves partial results.

## Participant contract

The current v2 participant item contains fields including:

- `id`;
- `price`;
- `action_price`;
- `max_action_price`;
- `current_boost`;
- `price_min_elastic`;
- `price_max_elastic`;
- `min_boost`;
- `max_boost`;
- optional `stock`;
- `add_mode`.

Price values are money objects (`amount` + `currency`). Boost values are numeric and are not money.

The current v2 participant schema does **not** provide the project's legacy `membership` or `availability` fields. The adapter therefore leaves them `None`; participant-list presence itself establishes that the requested product is currently returned as a participant. Fresh Check validates legacy membership/availability values only when those fields are actually present.

## Pagination

Both `/v2/actions/candidates` and `/v2/actions/products` use cursor pagination:

```text
limit + last_id
        ↓
response.last_id
        ↓
next request
```

The adapter follows the cursor until the returned page is empty, the cursor is absent, or the cursor repeats.

## Business semantics deliberately not inferred

The following remain outside the adapter contract:

- no Boost → price formula;
- no hard-coded 5% rule;
- no base-price mutation;
- no automatic stock decision for Elastic Boosting;
- no automatic retry after an unknown mutation outcome;
- no use of `activate` as an undocumented generic fallback; in this project it is the explicitly verified transport for both candidate ADD and existing-participant `action_price` UPDATE.

The application must treat business semantics separately from transport/schema validation and must continue to read back state after mutation.

## Current status

**D.2 PASS / D.3 contract reconciliation PASS.**

The separate `/v1/actions/products/update` path remains unverified and is blocked. Auto-Add DELETE is live-verified in this project. Auto-Add rollback is implemented against the current SDK's `/v2/actions/auto-add/products/update` contract and has been confirmed by the project's controlled rollback test; the result is retained in operation history/snapshot verification.

## ADD read-after-write reconciliation

After `POST /v1/actions/products/activate`, the application retries only the
read of current participants when a non-rejected product is not immediately
visible. The mutation itself is never retried automatically.

Application-level settings:

- `OZON_ADD_RECONCILIATION_READ_ATTEMPTS` — maximum number of participant READs (default `3`).
- `OZON_ADD_RECONCILIATION_READ_DELAY_SECONDS` — delay between READ attempts (default `1.0`).

These are application settings, not claims about Ozon API limits or Ozon's
consistency guarantees.

Classification remains fail-closed, with one explicit monetary read-back equivalence:

- `SUCCESS` — participant is visible and `action_price == requested`, **or** the read-back is the whole-RUB `ROUND_HALF_UP` representation of the requested price.
- `REJECTED` — Ozon explicitly returned the product in `rejected`.
- `PRICE_MISMATCH` — participant is visible but neither exact nor whole-RUB-equivalent to the requested price.
- `UNKNOWN_RESULT` — after the configured READ-only reconciliation attempts,
  the participant state is still not confirmed.

This does **not** introduce a new `normalized` status. A whole-RUB-equivalent
read-back is recorded as ordinary confirmed `SUCCESS`. For example, `885.60`
read back as `886` is accepted; for a source price of `1080`, that corresponds
to an effective discount of `17.962962...%`, which is treated as the requested
`18%` operation for reconciliation.

`price_min_elastic` and `price_max_elastic` are used for candidate ADD price-range validation before mutation. The final Fresh Check still compares the freshly returned values so a changed threshold blocks the stale calculation. They are not a substitute for read-after-write verification.

### REMOVE live forensic verification — 2026-10-04

A controlled real-account mutation was executed for Elastic Boosting action `1977747`:

- `product_id`: `6238154899`
- `sku`: `5710841509`
- `offer_id`: `2193`
- product: `Warhammer Old World, Великий Катай, Тяжелая кавалерия Чосона`

Before mutation, the participant had `action_price=1510`, `max_action_price=1510`,
`price_min_elastic=1510`, `price_max_elastic=1238`, and `current_boost=15`.

#### Attempt A — `/v1/actions/products/update`

Payload:

```json
{
  "action_id": 1977747,
  "products": [
    {
      "product_id": 6238154899,
      "action_price": {"amount": "1510", "currency": "RUB"}
    }
  ]
}
```

Live response:

```json
{
  "active_product_ids": [6238154899],
  "deactivated_product_ids": [],
  "rejected": [],
  "warnings": []
}
```

Read-after-write returned the product as still present. Therefore this endpoint is **not a verified REMOVE transport** for the tested Elastic Boosting action. In particular, the observed condition `action_price <= max_action_price` did not remove the participant.

#### Attempt B — `/v1/actions/products/deactivate`

Payload:

```json
{
  "action_id": 1977747,
  "product_ids": [6238154899]
}
```

Live response:

```json
{
  "result": {
    "product_ids": [6238154899],
    "rejected": []
  }
}
```

Read-after-write returned `still_present=false` and `product_ids=[6238154899]` in the forensic verifier's absence/presence check. Therefore REMOVE is **LIVE VERIFIED** for this exact Elastic Boosting action through `/v1/actions/products/deactivate` as of 2026-10-04.

The endpoint is deprecated in the local OpenAPI and scheduled for shutdown on 2026-10-13. This creates a time-bounded compatibility risk. The project must not silently substitute `/v2/actions/products/deactivate` for Elastic Boosting without a separate controlled verification, because the current OpenAPI description explicitly documents v2 as the Promocodes removal method while separately mentioning the update-based Elastic/Maximum path.

The application therefore keeps REMOVE transport isolated in `OzonPromotionsAdapter.deactivate_products()` and requires both mutation-response acknowledgement and read-after-write confirmation at the service layer.

### UI / price workflow regression fixes — 2026-10-04

Two price-management regressions were corrected after live/user acceptance testing:

- Participant UPDATE global percentage validation now passes the canonical service keys `price_min_elastic` / `price_max_elastic`. The UI previously supplied translated column labels, causing a `KeyError: 'price_min_elastic'` after an otherwise valid global percentage was entered.
- Candidate tables now expose an additional `Скидка` column. The displayed interval is calculated from the Ozon-returned `price`, `price_min_elastic`, and `price_max_elastic`; no fixed application discount limit is introduced.

### Safe rollback membership semantics — 2026-10-04

Rollback is now direction-aware:

- `ADD_PRODUCTS` rollback is a REMOVE membership mutation. It never sends the snapshot's candidate `action_price=0` through the activation contract.
- `REMOVE_PRODUCTS` rollback is an ADD membership mutation. It requires the product to be absent from current participants, present in current candidates, and restores the positive `action_price` recorded in the source snapshot after current threshold validation.
- `UPDATE_PRICE` rollback remains an `action_price` restoration for an existing participant and rejects non-positive snapshot targets.

All inverse membership paths retain a read-only prepare/Fresh Check stage and delegate the actual mutation to the already verified ADD/REMOVE services, which create their own pre-mutation snapshot and Fresh Check.
