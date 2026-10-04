> **Current release context — 04.10.2026:** Historical/date-specific findings in this document are preserved. Current release verification is **256 passed, 1 skipped** with `compileall` PASS. Known Promotions API shutdown risk is documented in `docs/API_RECONCILIATION.md` and `docs/RELEASE_AUDIT.md`.

# Stocks API Audit — 2026-10-03

## Scope

The Stocks section is independent from Promotions/Elastic Boosting. It uses Ozon Seller API for FBS/rFBS stock data and mutation only.

## Confirmed transport

| Operation | Method | Path | Purpose | Status |
|---|---|---|---|---|
| Stock by warehouse | POST | `/v2/product/info/stocks-by-warehouse/fbs` | Current `present`, `reserved`, `free_stock` by seller warehouse | CONFIRMED |
| Stock mutation | POST | `/v2/products/stocks` | Set free stock for a product–warehouse pair | CONFIRMED |
| Product cards | POST | `/v3/product/info/list` | Resolve product name/SKU for UI enrichment | Existing project contract |

The current stock-by-warehouse method requires `offer_id` or `sku` in the request. It is not a free-running catalogue pagination endpoint. The application paginates `/v3/product/list` with `filter.visibility=ALL` to collect seller `offer_id` values, then batches those identifiers into `/v2/product/info/stocks-by-warehouse/fbs`. The current schema explicitly allows up to 1000 `offer_id` values per request; the endpoint returns `products`, `cursor` and `has_next`. Each returned stock row is normalized into `sku`, `offer_id`, `product_id`, `present`, `reserved`, `free_stock`, `warehouse_id` and `warehouse_name` for the Stocks table. If catalog entries without `offer_id` occur, the application resolves their SKU through `/v3/product/info/list` and sends SKU batches separately because the API specifies `sku` as the alternative selector.

## Mutation semantics

`/v2/products/stocks` receives `stock`, which is the available/free quantity and does **not** include reserved units. The application therefore never converts `present` into the mutation value and never overwrites `reserved`.

The reviewed schema allows up to 100 product–warehouse pairs per mutation request. The adapter batches at that confirmed request boundary and does not retry mutation automatically.

## Fresh Check / Snapshot / Reconciliation

Every mutation follows:

```text
edit → Preview → Fresh Check → snapshot → explicit confirmation → mutation → read-after-write
```

If `present`, `reserved` or `free_stock` changed between Preview and mutation, the mutation is blocked and the user must refresh/recalculate.

A pre-mutation snapshot is persisted in SQLite. Mutation results are persisted per product–warehouse pair. A transport failure is never treated as success; if the transport result is unknown, the operation is recorded as `UNKNOWN_RESULT` and no blind retry is performed.

## Rate limiting / errors

The Ozon adapter classifies HTTP 429 as `RATE_LIMIT`. The UI shows a user-readable rate-limit state. No undocumented retry count or API-wide rate limit is hard-coded.

The `a-ulianov/OzonAPI` repository additionally documents an 80 requests/minute limit and a 30-second minimum between updates of the same product–warehouse pair for `/v2/products/stocks`. These values are treated as API-source evidence for audit purposes, not as application retry constants. The application does not fabricate a retry policy.

## Deprecated method

`/v1/product/import/stocks` is not used. Ozon's Seller API notifications state that this method was deprecated and removed from documentation in May 2025, with `/v2/products/stocks` as the replacement.

## FBO scope

The implemented management workflow is FBS/rFBS because `/v2/products/stocks` is the confirmed stock mutation endpoint for those schemes. FBO stock is a separate API/analytics concern and is not presented as if it were mutable through the FBS/rFBS mutation contract.

## Sources

1. Ozon Seller API documentation references embedded in the current Ozon-compatible SDK.
2. `a-ulianov/OzonAPI` current main branch, prices/stocks methods and schemas.
3. Ozon Seller API notification history confirming deprecation of `/v1/product/import/stocks` and the current `/v2/products/stocks` workflow.


## 2026-10-03 Contract correction — v2 request schema

The previous implementation queried the warehouse-stock endpoint once per Offer ID. That was an application-level inefficiency, not an API requirement. The current schema confirms `offer_id` is an array with a maximum of 1000 identifiers and `limit` is also capped at 1000. The adapter now batches identifiers at that confirmed boundary and keeps cursor pagination inside each batch.

This reduces the read path for a catalog of 893 products from potentially 893 stock HTTP calls to one stock request for the catalog batch (plus any additional cursor pages returned by Ozon).

The current `OzonAPI` Pydantic schema for `/v2/product/info/stocks-by-warehouse/fbs` defines:

- `offer_id: list[str] | None`;
- `sku: list[str] | None`;
- response fields `products`, `cursor`, `has_next`.

Therefore the adapter sends an explicit array even when querying one seller offer:

`{"offer_id": ["OFFER-ID"]}`

It does not send a scalar `offer_id`. Cursor pagination is applied to the stock endpoint itself. This correction is covered by regression tests. The schema is visible in the current OzonAPI repository.


## 02A — Mock Mutation Contract Verification — 2026-10-03

Verified without real Ozon writes:

- absolute stock update lifecycle `old → Preview → Fresh Check → snapshot → mutation → read-after-write`;
- actual `present`, `reserved`, `free_stock` values are persisted after verification;
- Fresh Check blocks changes to `present`, `reserved` or `free_stock`;
- normal partial responses are persisted per product–warehouse pair;
- transport timeout is `UNKNOWN_RESULT` and is never blindly retried;
- HTTP 429 is `RATE_LIMIT` and is never blindly retried;
- 101 mutation records are split into 100 + 1 requests;
- rollback is prepared from the immutable original stock snapshot and executed through the same safety boundary;
- existing 900-product no-real-Ozon stress scenario remains passing.

No real Ozon mutation was performed during 02A. Live write/read-after-write verification remains a separate controlled integration step.

## 02A QA hardening update — 2026-10-03

Additional Mock/API safety verification completed against the current project build:

- read-after-write transport failure after a successful mutation response → operation and affected successful items become `UNKNOWN_RESULT`; no mutation retry;
- duplicate product–warehouse pair → rejected before snapshot/mutation;
- negative requested free stock → rejected before snapshot/mutation;
- 900 mutation records → 9 transport batches of 100 in the adapter contract test, without real Ozon writes;
- second mutation batch returning HTTP 429 → first batch is not resent and the 429 is surfaced as `RATE_LIMIT`;
- existing timeout, normal partial-response, Fresh Check, rollback and 900-product mock scenarios remain passing.

This QA does not establish undocumented Ozon retry guarantees. It establishes the application's fail-closed behavior when transport or verification outcomes are ambiguous.

## 02B — Combined Mutation Hardening / Release Gate Audit — 2026-10-03

Implemented in one patch on top of Stocks QA 02A:

- terminal stock operation cannot be executed twice;
- mutation is blocked if `operation_id` / `snapshot_id` are missing, mismatched, or the persisted snapshot is absent;
- read-after-write transport failure remains `UNKNOWN_RESULT` and cannot be retried blindly;
- second-batch 429 is modeled with a real 100 + 1 split: the first 100 are not resent and the second batch is not retried;
- 900-record service stress now exercises nine 100-item adapter batches without real Ozon writes;
- Stocks History exposes `Подготовить rollback`; rollback uses the persisted source snapshot, performs Fresh Check, creates a new snapshot and reuses the same confirmation/mutation path;
- UI exposes `UNKNOWN_RESULT` as a distinct non-success state and explicitly prohibits retry from the result message.

The application does not hard-code a retry count or Ozon-wide rate limit.

## Current status

Automated verification: PASS — 234 tests.
Python compile check: PASS.
Security source scan: no real credential pattern found; the only matches for credential field names are application variable names/UI keys, not credential values.
Real Ozon mutation was not used for negative/error injection in this patch.
