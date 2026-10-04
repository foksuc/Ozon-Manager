# Current release status — 2026-10-04

- Local target: **one user**.
- Automated QA: **256 passed, 1 skipped**.
- Python compile check: **PASS**.
- Current documented functionality is preserved; this update changes documentation only.
- Known planned API compatibility risk: legacy Promotions mutation transports are scheduled for Ozon shutdown on **13.10.2026**. Replacement is intentionally not claimed until verified.

---

# MVP Requirements

## Functional

- list promotions;
- identify/select Elastic Boosting;
- load participants;
- select SKU(s);
- read current state;
- set explicit action_price;
- Preview;
- Fresh Check;
- immutable Snapshot;
- explicit Confirmation;
- action_price mutation **only when the Ozon mutation contract is independently verified**;
- read-after-write;
- per-SKU verification;
- partial results;
- History;
- Snapshot-based rollback.

## Safety

Target Boost is BLOCKED. Base price is never mutated. No guessed boost formula exists. No blind mutation retry exists.

## Elastic Boosting candidate ADD price bounds

For ordinary candidate → participant ADD, the application must calculate a
per-product discount interval from the Ozon-returned `price_min_elastic` and
`price_max_elastic` values. The ADD price must satisfy:

`price_max_elastic ≤ new_price ≤ price_min_elastic`

The UI must display the calculated minimum and maximum discount percentages
and their corresponding threshold prices. Missing or inconsistent thresholds
must block ADD fail-closed.


## Current UI / bulk price requirements

### Participant UPDATE — global percentage

- The user may select a percentage from predefined UI choices or enter another percentage manually.
- The selected percentage is evaluated independently against every selected participant's current `price_min_elastic` / `price_max_elastic` range.
- A percentage below any participant's required minimum is rejected and the package remains unchanged.
- A percentage above any participant's maximum is also rejected fail-closed.
- When all products pass, the same percentage is converted to an absolute price separately for each product.
- No fixed application-side `1%–18%` limit is used for Participant UPDATE.

### Loading UX

Every operation that performs Ozon reads, Fresh Check, snapshot work, mutation or read-after-write verification must expose a centered loading modal. The modal must not change the mutation safety contract and must disappear after the operation finishes or fails.

### Interactive tables

Selectable tables must support header `✓` select-all for visible rows and Shift+LMB / Shift+RMB visible-range selection. Table frames must remain independently scrollable without forcing page-level scrolling for ordinary desktop use.

## Stocks section — implemented 2026-10-03

- Real Ozon Seller API reads for FBS/rFBS stock by warehouse.
- Product/warehouse table with product name, SKU, Offer ID, Product ID, warehouse, present, reserved and free stock.
- Search by name/SKU/Offer ID/Product ID.
- Warehouse and availability filters.
- Numeric/text sorting through the shared operational table component.
- UI pagination over the loaded cursor-paginated API result.
- Inline free-stock editing and selected-product bulk editing.
- Preview before mutation.
- Fresh Check immediately before mutation.
- Mandatory SQLite snapshot before mutation.
- Explicit confirmation for mutation.
- Per-product/warehouse API result handling and read-after-write reconciliation.
- Partial/unknown transport results are persisted and never blindly retried.
- Dedicated stock operation history, independent from promotion history.

## 2026-10-04 regression clarifications

- Candidate Elastic Boosting tables must display the Ozon-derived discount interval alongside price thresholds.
- Global Participant UPDATE percentage application must validate every selected product against its own Ozon-derived interval without relying on translated UI field names.
- Safe rollback must invert membership operations: ADD→REMOVE and REMOVE→ADD; it must never submit a non-positive candidate snapshot price to the activation mutation.
