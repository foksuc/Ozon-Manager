# API Contract — Current release addendum 2026-10-04

## Source hierarchy

1. Ozon Seller API published documentation/OpenAPI.
2. Bundled Ozon Seller API forensic snapshot / OpenAPI checked 2026-10-03 and reviewed for this release on 2026-10-04.
3. Project adapter and contract tests.


> **Current release note — 04.10.2026:** The mutation endpoints currently used by the adapter remain the live-verified legacy transports. The bundled API reference schedules `POST /v1/actions/products/activate` and `POST /v1/actions/products/deactivate` for shutdown on **13.10.2026**. No unverified replacement is documented here as implemented.

## Verified operations

| Operation | Method | Path | Request | Response |
|---|---|---|---|---|
| Promotions | GET | `/v1/actions` | none | `result[]` |
| Candidates | POST | `/v2/actions/candidates` | `action_id`, `limit`, `last_id` | `products`, `total`, `last_id` |
| Participants | POST | `/v2/actions/products` | `action_id`, `limit`, `last_id` | `products`, `total`, `last_id` |
| Action-price mutation / ADD | POST | `/v1/actions/products/activate` | `action_id`, `products[{product_id, action_price, stock?}]` | `result.product_ids`, `result.rejected` |
| Activate products (ADD / live-verified existing participant update) | POST | `/v1/actions/products/activate` | `action_id`, `products[{product_id, action_price, stock?}]` | `result.product_ids`, `result.rejected` |
| Deactivate products (REMOVE) | POST | `/v1/actions/products/deactivate` | `action_id`, `product_ids` | `result.product_ids`, `result.rejected` | **LIVE VERIFIED for Elastic action 1977747 on 2026-10-04; deprecated, scheduled for shutdown 2026-10-13** |

## REMOVE live verification

For Elastic Boosting action `1977747`, product `6238154899` / SKU `5710841509` was removed successfully through `POST /v1/actions/products/deactivate`. Ozon returned the target in `result.product_ids` with `rejected=[]`, and the subsequent `/v2/actions/products` read no longer contained the product. This endpoint is deprecated and scheduled for shutdown on 2026-10-13; no replacement for Elastic Boosting is considered verified by this test.

The application therefore requires both mutation-response acknowledgement and read-after-write absence before recording REMOVE as successful.

## Candidate vs participant behavior

`/v2/actions/candidates` and `/v2/actions/products` are intentionally kept separate.
The UI does not treat candidates as price-mutation targets.
A selected candidate can be explicitly added to the promotion through `/v1/actions/products/activate`. Existing participant price UPDATE also reaches Ozon through the same live-verified activate transport, exposed by the adapter as `update_products()`; the old `/v1/actions/products/update` endpoint is not called. ADD and UPDATE remain separate application workflows with their own Preview/Fresh Check/Snapshot/Confirmation gates.

## Activate / action-price wire contract

The current published contract exposes:

```json
{
  "action_id": 1977747,
  "products": [
    {
      "product_id": 1508648261,
      "action_price": 1005,
      "stock": 1
    }
  ]
}
```

For the existing Elastic Boosting participant above, this contract was also verified live: changing `action_price` through `/v1/actions/products/activate` was accepted and confirmed by read-after-write.

The exact maximum number of products per request is **UNKNOWN for the current contract** and is not hard-coded as an Ozon API limit by this reconciliation.

## Partial results

The activate/deactivate response separates accepted product IDs from `rejected` entries under `result`.

The application must preserve these categories and perform read-after-write verification. HTTP 200 alone is not business success.

## Reads and pagination

The current candidate and participant operations use `/v2/...` and cursor `last_id`. The adapter no longer relies on the legacy `/v1/actions/candidates` or `/v1/actions/products` response envelope.

## Participant mapping

Current v2 participant price fields are money objects. Boost fields are numeric. `membership` and `availability` are not part of the current v2 participant schema; they remain optional compatibility fields in the domain model rather than fabricated adapter values.

## Safety constraints

The application continues to prohibit:

- target Boost formula mutation;
- base-price mutation;
- blind mutation retry;
- interpreting HTTP 200 as universal business success;
- mutation without Preview, Fresh Check, Snapshot and explicit Confirmation;
- calling `/v1/actions/products/update`; the adapter intentionally routes Participant UPDATE through the verified `/v1/actions/products/activate` transport.

## Live verification

The activate transport is live-verified for an existing Elastic Boosting participant: Ozon accepted the requested `action_price` and the project confirmed the resulting value through read-after-write. The same adapter transport is used by Participant UPDATE. The application still treats read-after-write as mandatory and does not infer business success from HTTP status alone.

## Product Info / card enrichment

`POST /v3/product/info/list` is used as the read-only Product ID → product-card enrichment boundary. The current documented contract allows up to 1000 identifiers in one request. The application parses the raw response directly for `id`, `name`, and `sources[].sku` instead of relying on the SDK response model, because the SDK model declares many unrelated response fields as required and can reject an otherwise usable live response.


### Auto-Add Ozon
The Auto-Add list response provides `price` and `action_price_to_auto_add`. The UI derives the informational `Скидка` percentage locally; no `discount_percent` field is assumed. Local threshold filtering does not perform mutation.

### Auto-Add deletion mutation
Current application adapter contract:

`POST /v1/actions/auto-add/products/delete`

Payload used by the application:
- `action_id`
- `auto_add_date` — the exact date previously returned by Ozon in `/v1/actions.auto_add_dates` and used by the Auto-Add list read
- `product_ids`

The application does not invent a date and does not retry this mutation. Before mutation it performs Preview → Fresh Check → Snapshot → explicit confirmation → final Fresh Check. After the mutation it performs a read-only reconciliation through `/v1/actions/auto-add/products/list`.

**Contract status:** the project has a live-verified DELETE path for the current account (`/v1/.../delete`). A current Ozon-compatible Go SDK additionally exposes the newer V2 model with the same `action_id` + `auto_add_date` + `product_ids` shape. The application keeps the already live-verified v1 DELETE path and does not silently switch it.

### Auto-Add rollback / restore mutation

Rollback uses the dedicated Auto-Add update contract, not participant `activate`. The current SDK source exposes:

`POST /v2/actions/auto-add/products/update`

Payload model:
- `action_id`
- `auto_add_date`
- `products[]`
- `products[].id`
- `products[].action_price` as a money object (`amount`, `currency`)
- optional `products[].stock`

The SDK documents this operation as **add or update products in scheduled Auto-Add** and its response can contain `product_ids`, `deactivated_ids`, `rejected`, `warnings` and price-validation diagnostics. This is sufficient to implement the adapter and mock/contract tests, but the exact endpoint/path remains **LIVE_VERIFICATION_UNKNOWN** until a controlled real-account rollback test captures the response. The controlled project rollback test has confirmed the Auto-Add restore workflow. The adapter nevertheless keeps the SDK-derived request/response model isolated behind the adapter and does not generalize this controlled result into an undocumented Ozon-wide limit or guarantee.

## Stocks — reconciled 2026-10-03

The Stocks section is independent from Promotions.

| Operation | Method | Path | Notes |
|---|---|---|---|
| FBS/rFBS stock by warehouse | POST | `/v2/product/info/stocks-by-warehouse/fbs` | Requires `offer_id` or `sku`; current schema accepts up to 1000 identifiers per request and returns `products`, `cursor`, `has_next`. Application paginates `/v3/product/list` first and batches catalog `offer_id` values up to the confirmed 1000-identifier contract boundary |
| FBS/rFBS stock mutation | POST | `/v2/products/stocks` | `stock` is free stock; adapter batches at 100 product–warehouse pairs |

`/v1/product/import/stocks` is deprecated and is not used.

The application treats 429 as `RATE_LIMIT`, never retries mutations blindly, and requires Preview → Fresh Check → Snapshot → Confirmation → Mutation → Read-after-write for stock changes.
