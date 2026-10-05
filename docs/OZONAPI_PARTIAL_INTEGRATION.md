> **Current release context — 04.10.2026:** Historical/date-specific findings in this document are preserved. Current release verification is **256 passed, 1 skipped** with `compileall` PASS. Known Promotions API shutdown risk is documented in `docs/API_RECONCILIATION.md` and `docs/RELEASE_AUDIT.md`.

# OzonAPI — Partial Integration Audit

Date: 2026-10-01

## Integrated

| Operation | OzonAPI | Application | Decision |
|---|---|---|---|
| `GET /v1/actions` | `SellerAPI.actions()` | `OzonSDKPromotionsReader` | INTEGRATED |
| Candidate read | SDK has legacy `ActionProduct` model | direct adapter | NOT INTEGRATED |
| Participant read | SDK has legacy `ActionProduct` model | direct adapter | NOT INTEGRATED |
| `POST /v1/actions/products/activate` | present in current Promotions contract and live-verified for action-price update | direct adapter | USE / READ-AFTER-WRITE REQUIRED |
| Elastic Boosting price field via `/v1/product/import/prices` | SDK exposes legacy `manage_elastic_boosting_through_price` | not used | DO NOT USE |

## Why the boundary is narrow

The SDK `ActionProduct` model exposes a reduced product shape (`id`, `price`, `action_price`, `max_action_price`, `add_mode`, stock fields, SKU). The application's current participant model also carries Elastic Boosting fields such as `current_boost`, `min_boost`, `max_boost`, `price_min_elastic`, and `price_max_elastic`. Delegating these reads through the SDK would risk silently discarding fields.

The SDK also exposes `manage_elastic_boosting_through_price` on `/v1/product/import/prices`, but this is not accepted as the current Elastic Boosting mutation mechanism without current official confirmation.

## Runtime switch

`OZON_USE_SDK=1` enables the SDK-backed `/v1/actions` read path. `OZON_USE_SDK=0` keeps the direct HTTP read path. The test suite explicitly disables SDK use for transport-level adapter tests.

## Safety status

No mutation is moved into OzonAPI by this change. Existing Preview → Fresh Check → Snapshot → Confirmation → Mutation → Read-after-write controls remain in the application layer.

The update endpoint remains a separate contract gate and must not be considered SDK-verified.
